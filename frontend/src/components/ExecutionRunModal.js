import React, { useState, useEffect } from 'react';
import { connectionsAPI, executionAPI } from '../services/api';
import { XMarkIcon, PlayIcon, PlusIcon, BoltIcon, DocumentTextIcon } from '@heroicons/react/24/outline';

/**
 * ExecutionRunModal -- Configure and launch a test execution run.
 *
 * Supports three connection types:
 *   - API (HTTP)       — base_url, auth
 *   - Database (SQL)   — database URL / connection string
 *   - Browser (UI)     — app URL, login credentials, Playwright selectors
 *
 * Props:
 *   projectId     — UUID of the project
 *   testCaseIds   — Array of selected test case UUIDs
 *   testCaseCount — Number of selected test cases (for display)
 *   onClose       — Close handler
 *   onStarted     — Callback when run is created (receives run object)
 */

const CONNECTION_TYPES = [
  { key: 'api', label: 'API (HTTP)', icon: '🌐', desc: 'REST/HTTP API testing — smoke tests, CRUD lifecycle' },
  { key: 'database', label: 'Database (SQL)', icon: '🗄️', desc: 'SQL queries, ETL/ELT reconciliation, data quality' },
  { key: 'browser', label: 'Browser (UI)', icon: '🖥️', desc: 'Playwright browser automation — UI flows, E2E tests' },
];

export default function ExecutionRunModal({ projectId, testCaseIds, testCaseCount, onClose, onStarted }) {
  // Connection type selector
  const [connectionType, setConnectionType] = useState('api');

  // Connection state
  const [connections, setConnections] = useState([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState('');
  const [showNewConnection, setShowNewConnection] = useState(false);

  // API connection form
  const [newConn, setNewConn] = useState({
    name: '', base_url: '', auth_type: 'none', auth_token: '',
  });

  // Database connection form
  const [newDbConn, setNewDbConn] = useState({
    name: '', db_url: '', db_type: 'postgresql',
    source_db_url: '', target_db_url: '', // for reconciliation
  });

  // Browser connection form
  const [newBrowserConn, setNewBrowserConn] = useState({
    name: '', app_url: '', login_url: '',
    username: '', password: '',
    username_selector: '#username, #email, input[name="email"]',
    password_selector: '#password, input[name="password"]',
    submit_selector: 'button[type="submit"]',
    viewport_width: 1280, viewport_height: 720,
  });

  const [creatingConn, setCreatingConn] = useState(false);

  // Execution context
  const [executionContext, setExecutionContext] = useState('');
  const [showContext, setShowContext] = useState(false);

  // Run state
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadConnections();
  }, [connectionType]);

  const driverForType = (t) => {
    if (t === 'api') return 'http';
    if (t === 'database') return 'jdbc';
    if (t === 'browser') return 'playwright';
    return 'http';
  };

  const loadConnections = async () => {
    try {
      const res = await connectionsAPI.getAll({ type: connectionType });
      setConnections(res.data);
      if (res.data.length > 0) {
        setSelectedConnectionId(res.data[0].id);
      } else {
        setSelectedConnectionId('');
        setShowNewConnection(true);
      }
    } catch (err) {
      console.error('Failed to load connections:', err);
    }
  };

  const handleCreateConnection = async (e) => {
    e.preventDefault();
    setCreatingConn(true);
    setError('');

    try {
      let name, config;

      if (connectionType === 'api') {
        name = newConn.name.trim();
        if (!name || !newConn.base_url.trim()) {
          setError('Connection name and base URL are required.');
          setCreatingConn(false);
          return;
        }
        config = { base_url: newConn.base_url.trim() };
        if (newConn.auth_type !== 'none') {
          config.auth_type = newConn.auth_type;
          config.auth_token = newConn.auth_token;
        }
      } else if (connectionType === 'database') {
        name = newDbConn.name.trim();
        if (!name || !newDbConn.db_url.trim()) {
          setError('Connection name and database URL are required.');
          setCreatingConn(false);
          return;
        }
        config = {
          db_url: newDbConn.db_url.trim(),
          db_type: newDbConn.db_type,
        };
        if (newDbConn.source_db_url.trim()) config.source_db_url = newDbConn.source_db_url.trim();
        if (newDbConn.target_db_url.trim()) config.target_db_url = newDbConn.target_db_url.trim();
      } else if (connectionType === 'browser') {
        name = newBrowserConn.name.trim();
        if (!name || !newBrowserConn.app_url.trim()) {
          setError('Connection name and app URL are required.');
          setCreatingConn(false);
          return;
        }
        config = {
          app_url: newBrowserConn.app_url.trim(),
          base_url: newBrowserConn.app_url.trim(), // alias for engine compat
          viewport_width: newBrowserConn.viewport_width || 1280,
          viewport_height: newBrowserConn.viewport_height || 720,
        };
        if (newBrowserConn.login_url.trim()) config.login_url = newBrowserConn.login_url.trim();
        if (newBrowserConn.username.trim()) config.login_username = newBrowserConn.username.trim();
        if (newBrowserConn.password.trim()) config.login_password = newBrowserConn.password.trim();
        if (newBrowserConn.username_selector.trim()) config.login_username_selector = newBrowserConn.username_selector.trim();
        if (newBrowserConn.password_selector.trim()) config.login_password_selector = newBrowserConn.password_selector.trim();
        if (newBrowserConn.submit_selector.trim()) config.login_submit_selector = newBrowserConn.submit_selector.trim();
      }

      if (executionContext.trim()) {
        config.execution_context = executionContext.trim();
      }

      const res = await connectionsAPI.create({
        name,
        type: connectionType,
        driver: driverForType(connectionType),
        config,
      });
      setSelectedConnectionId(res.data.id);
      setShowNewConnection(false);
      loadConnections();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create connection.');
    } finally {
      setCreatingConn(false);
    }
  };

  const handleStartRun = async () => {
    if (!selectedConnectionId) {
      setError('Please select or create a connection.');
      return;
    }

    // Attach execution context to existing connection if provided
    if (executionContext.trim() && selectedConnectionId) {
      try {
        const conn = connections.find(c => c.id === selectedConnectionId);
        if (conn) {
          await connectionsAPI.update(selectedConnectionId, {
            config: { ...conn.config, execution_context: executionContext.trim() },
          });
        }
      } catch (err) {
        console.warn('Could not update connection with execution context:', err);
      }
    }

    setStarting(true);
    setError('');
    try {
      const res = await executionAPI.create({
        project_id: projectId,
        test_case_ids: testCaseIds,
        connection_id: selectedConnectionId,
      });
      onStarted(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else if (Array.isArray(detail)) setError(detail.map(d => d.msg || String(d)).join('; '));
      else setError('Failed to start execution run.');
      setStarting(false);
    }
  };

  const contextPlaceholderForType = () => {
    if (connectionType === 'api') {
      return `Provide additional context for AI parameter extraction:\n\n• Swagger/OpenAPI spec snippets\n• API endpoint documentation\n• Authentication flow details\n• Request/response format examples`;
    } else if (connectionType === 'database') {
      return `Provide ETL/ELT context for SQL test generation:\n\n• Source → Target table mappings\n• Column mapping rules\n• Business transformation logic\n• Data quality rules (NOT NULL, unique, range)\n• Freshness/SLA requirements`;
    } else {
      return `Provide UI testing context:\n\n• Page structure / navigation flow\n• Important CSS selectors or data-testid attributes\n• Dynamic elements to wait for\n• Known UI quirks or loading patterns`;
    }
  };

  const howItWorksSteps = () => {
    if (connectionType === 'api') {
      return [
        '1. AI reads each test case to extract HTTP parameters (method, endpoint, body)',
        '2. Matches to best template (smoke test / CRUD lifecycle)',
        '3. Executes HTTP requests against your API connection',
        '4. Reports pass/fail for each assertion with request/response logs',
      ];
    } else if (connectionType === 'database') {
      return [
        '1. AI reads each test case to extract SQL queries and validation rules',
        '2. Matches to template (single query / source-target reconciliation)',
        '3. Executes SQL against your database connection',
        '4. Validates row counts, column values, aggregates, and data freshness',
      ];
    } else {
      return [
        '1. AI reads each test case to extract browser actions (click, fill, navigate)',
        '2. Launches a headless Chromium browser via Playwright',
        '3. Optionally logs in using your credentials, then executes step-by-step',
        '4. Validates visibility, text content, URLs; captures screenshots on failure',
      ];
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto animate-slide-up">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center">
                <BoltIcon className="w-5 h-5 text-teal-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-fg-navy">Run Test Execution</h2>
                <p className="text-xs text-fg-mid">{testCaseCount} test case{testCaseCount !== 1 ? 's' : ''} selected</p>
              </div>
            </div>
            <button onClick={onClose} className="text-fg-mid hover:text-fg-dark">
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Connection type selector */}
          <div className="mb-5">
            <label className="label mb-2">Execution Type</label>
            <div className="grid grid-cols-3 gap-2">
              {CONNECTION_TYPES.map((ct) => (
                <button
                  key={ct.key}
                  onClick={() => { setConnectionType(ct.key); setShowNewConnection(false); setError(''); }}
                  className={`p-3 rounded-lg border-2 text-center transition-all ${
                    connectionType === ct.key
                      ? 'border-teal-500 bg-teal-50'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                  }`}
                >
                  <span className="text-xl block mb-1">{ct.icon}</span>
                  <span className="text-xs font-semibold text-fg-dark block">{ct.label}</span>
                </button>
              ))}
            </div>
            <p className="text-xs text-fg-mid mt-1.5">
              {CONNECTION_TYPES.find(ct => ct.key === connectionType)?.desc}
            </p>
          </div>

          {/* Connection selection */}
          <div className="mb-5">
            <label className="label">
              {connectionType === 'api' ? 'API Connection' :
               connectionType === 'database' ? 'Database Connection' :
               'Browser Connection'}
            </label>
            {connections.length > 0 ? (
              <div className="space-y-2">
                <select
                  value={selectedConnectionId}
                  onChange={(e) => setSelectedConnectionId(e.target.value)}
                  className="input-field"
                >
                  {connections.map((conn) => (
                    <option key={conn.id} value={conn.id}>
                      {conn.name} — {conn.config?.base_url || conn.config?.app_url || conn.config?.db_url || 'No URL'}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setShowNewConnection(!showNewConnection)}
                  className="text-xs text-fg-teal hover:text-fg-tealDark flex items-center gap-1"
                >
                  <PlusIcon className="w-3 h-3" />
                  {showNewConnection ? 'Cancel' : 'Create new connection'}
                </button>
              </div>
            ) : (
              <div className="text-sm text-fg-mid mb-2">
                No {connectionType} connections found. Create one below.
              </div>
            )}
          </div>

          {/* Quick-create connection form — API */}
          {(showNewConnection || connections.length === 0) && connectionType === 'api' && (
            <div className="mb-5 p-4 rounded-lg bg-gray-50 border border-gray-200 animate-fade-in">
              <h4 className="text-sm font-semibold text-fg-dark mb-3">New API Connection</h4>
              <form onSubmit={handleCreateConnection} className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-fg-mid">Connection Name</label>
                  <input value={newConn.name} onChange={(e) => setNewConn({ ...newConn, name: e.target.value })}
                    placeholder="e.g., Production API" className="input-field mt-1" autoFocus />
                </div>
                <div>
                  <label className="text-xs font-medium text-fg-mid">Base URL</label>
                  <input value={newConn.base_url} onChange={(e) => setNewConn({ ...newConn, base_url: e.target.value })}
                    placeholder="https://api.example.com" className="input-field mt-1" />
                </div>
                <div>
                  <label className="text-xs font-medium text-fg-mid">Auth Type</label>
                  <select value={newConn.auth_type} onChange={(e) => setNewConn({ ...newConn, auth_type: e.target.value })}
                    className="input-field mt-1">
                    <option value="none">None</option>
                    <option value="bearer">Bearer Token</option>
                    <option value="api_key">API Key</option>
                  </select>
                </div>
                {newConn.auth_type !== 'none' && (
                  <div className="animate-fade-in">
                    <label className="text-xs font-medium text-fg-mid">
                      {newConn.auth_type === 'bearer' ? 'Bearer Token' : 'API Key'}
                    </label>
                    <input value={newConn.auth_token} onChange={(e) => setNewConn({ ...newConn, auth_token: e.target.value })}
                      placeholder={newConn.auth_type === 'bearer' ? 'eyJ...' : 'your-api-key'}
                      className="input-field mt-1" type="password" />
                  </div>
                )}
                <div className="flex justify-end">
                  <button type="submit" disabled={creatingConn} className="btn-secondary text-sm">
                    {creatingConn ? 'Creating...' : 'Create Connection'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Quick-create connection form — Database */}
          {(showNewConnection || connections.length === 0) && connectionType === 'database' && (
            <div className="mb-5 p-4 rounded-lg bg-gray-50 border border-gray-200 animate-fade-in">
              <h4 className="text-sm font-semibold text-fg-dark mb-3">New Database Connection</h4>
              <form onSubmit={handleCreateConnection} className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-fg-mid">Connection Name</label>
                  <input value={newDbConn.name} onChange={(e) => setNewDbConn({ ...newDbConn, name: e.target.value })}
                    placeholder="e.g., Staging PostgreSQL" className="input-field mt-1" autoFocus />
                </div>
                <div>
                  <label className="text-xs font-medium text-fg-mid">Database Type</label>
                  <select value={newDbConn.db_type} onChange={(e) => setNewDbConn({ ...newDbConn, db_type: e.target.value })}
                    className="input-field mt-1">
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="mssql">SQL Server</option>
                    <option value="oracle">Oracle</option>
                    <option value="snowflake">Snowflake</option>
                    <option value="databricks">Databricks</option>
                    <option value="bigquery">BigQuery</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-fg-mid">Database URL (primary)</label>
                  <input value={newDbConn.db_url} onChange={(e) => setNewDbConn({ ...newDbConn, db_url: e.target.value })}
                    placeholder="postgresql://user:pass@host:5432/dbname" className="input-field mt-1 font-mono text-xs" />
                </div>
                <div className="p-3 rounded bg-blue-50 border border-blue-100">
                  <p className="text-xs font-semibold text-blue-800 mb-2">For ETL/ELT Reconciliation (optional)</p>
                  <div className="space-y-2">
                    <div>
                      <label className="text-xs font-medium text-fg-mid">Source DB URL</label>
                      <input value={newDbConn.source_db_url} onChange={(e) => setNewDbConn({ ...newDbConn, source_db_url: e.target.value })}
                        placeholder="postgresql://user:pass@source-host:5432/source_db" className="input-field mt-1 font-mono text-xs" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-fg-mid">Target DB URL</label>
                      <input value={newDbConn.target_db_url} onChange={(e) => setNewDbConn({ ...newDbConn, target_db_url: e.target.value })}
                        placeholder="postgresql://user:pass@target-host:5432/target_db" className="input-field mt-1 font-mono text-xs" />
                    </div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button type="submit" disabled={creatingConn} className="btn-secondary text-sm">
                    {creatingConn ? 'Creating...' : 'Create Connection'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Quick-create connection form — Browser */}
          {(showNewConnection || connections.length === 0) && connectionType === 'browser' && (
            <div className="mb-5 p-4 rounded-lg bg-gray-50 border border-gray-200 animate-fade-in">
              <h4 className="text-sm font-semibold text-fg-dark mb-3">New Browser Connection</h4>
              <form onSubmit={handleCreateConnection} className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-fg-mid">Connection Name</label>
                  <input value={newBrowserConn.name} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, name: e.target.value })}
                    placeholder="e.g., Staging App" className="input-field mt-1" autoFocus />
                </div>
                <div>
                  <label className="text-xs font-medium text-fg-mid">Application URL</label>
                  <input value={newBrowserConn.app_url} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, app_url: e.target.value })}
                    placeholder="https://app.example.com" className="input-field mt-1" />
                </div>
                <div className="p-3 rounded bg-blue-50 border border-blue-100">
                  <p className="text-xs font-semibold text-blue-800 mb-2">Login Configuration (optional)</p>
                  <div className="space-y-2">
                    <div>
                      <label className="text-xs font-medium text-fg-mid">Login URL</label>
                      <input value={newBrowserConn.login_url} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, login_url: e.target.value })}
                        placeholder="https://app.example.com/login" className="input-field mt-1 text-xs" />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs font-medium text-fg-mid">Username</label>
                        <input value={newBrowserConn.username} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, username: e.target.value })}
                          placeholder="user@example.com" className="input-field mt-1 text-xs" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-fg-mid">Password</label>
                        <input value={newBrowserConn.password} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, password: e.target.value })}
                          placeholder="••••••••" className="input-field mt-1 text-xs" type="password" />
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-fg-mid">Username Selector</label>
                      <input value={newBrowserConn.username_selector} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, username_selector: e.target.value })}
                        className="input-field mt-1 font-mono text-xs" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-fg-mid">Password Selector</label>
                      <input value={newBrowserConn.password_selector} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, password_selector: e.target.value })}
                        className="input-field mt-1 font-mono text-xs" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-fg-mid">Submit Button Selector</label>
                      <input value={newBrowserConn.submit_selector} onChange={(e) => setNewBrowserConn({ ...newBrowserConn, submit_selector: e.target.value })}
                        className="input-field mt-1 font-mono text-xs" />
                    </div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button type="submit" disabled={creatingConn} className="btn-secondary text-sm">
                    {creatingConn ? 'Creating...' : 'Create Connection'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Execution Context */}
          <div className="mb-5">
            <button
              onClick={() => setShowContext(!showContext)}
              className="flex items-center gap-2 text-sm font-medium text-fg-dark hover:text-fg-tealDark transition-colors"
            >
              <DocumentTextIcon className="w-4 h-4" />
              Execution Context
              <span className="text-xs text-fg-mid font-normal">(optional)</span>
              <span className="text-xs text-fg-mid ml-auto">{showContext ? '▲' : '▼'}</span>
            </button>

            {showContext && (
              <div className="mt-3 animate-fade-in">
                <textarea
                  value={executionContext}
                  onChange={(e) => setExecutionContext(e.target.value)}
                  placeholder={contextPlaceholderForType()}
                  rows={6}
                  className="input-field text-xs font-mono"
                />
                <p className="text-xs text-fg-mid mt-1">
                  The AI uses this alongside your test cases to extract the right parameters for execution.
                </p>
              </div>
            )}
          </div>

          {/* How it works */}
          <div className="mb-6 p-4 rounded-lg bg-blue-50 border border-blue-100">
            <h4 className="text-sm font-semibold text-blue-800 mb-2">How it works</h4>
            <ul className="text-xs text-blue-700 space-y-1">
              {howItWorksSteps().map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button
              onClick={handleStartRun}
              disabled={starting || !selectedConnectionId}
              className="btn-primary flex items-center gap-2"
            >
              <PlayIcon className="w-4 h-4" />
              {starting ? 'Starting...' : 'Start Execution'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

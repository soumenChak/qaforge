import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { testCasesAPI, projectsAPI, executionsAPI } from '../services/api';
import Breadcrumb from '../components/Breadcrumb';
import RatingWidget from '../components/RatingWidget';
import ProofViewer from '../components/ProofViewer';
import {
  TrashIcon,
  PlusIcon,
  ArrowsUpDownIcon,
  XMarkIcon,
  ChevronDownIcon,
  ClockIcon,
  DocumentMagnifyingGlassIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/solid';

/* ── Spec Details helpers ─────────────────────────────────────────────── */
const STEP_TYPES = [
  { value: '', label: 'None' },
  { value: 'mcp', label: 'MCP Tool' },
  { value: 'api', label: 'REST API' },
  { value: 'sql', label: 'SQL Query' },
  { value: 'ui', label: 'UI Action' },
  { value: 'manual', label: 'Manual' },
];

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

function JsonField({ label, value, onChange, rows = 3, placeholder }) {
  const [raw, setRaw] = useState(() => {
    if (!value) return '';
    return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  });
  const [jsonErr, setJsonErr] = useState('');

  const handleBlur = () => {
    if (!raw.trim()) {
      setJsonErr('');
      onChange(null);
      return;
    }
    try {
      const parsed = JSON.parse(raw);
      setJsonErr('');
      onChange(parsed);
    } catch {
      setJsonErr('Invalid JSON');
    }
  };

  // sync external value changes
  useEffect(() => {
    if (value === null || value === undefined) {
      setRaw('');
    } else {
      const next = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
      setRaw(prev => {
        try { if (JSON.stringify(JSON.parse(prev)) === JSON.stringify(value)) return prev; } catch {}
        return next;
      });
    }
  }, [value]);

  return (
    <div>
      <label className="text-xs font-medium text-fg-mid">{label}</label>
      <textarea
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        onBlur={handleBlur}
        rows={rows}
        className={`input-field text-xs font-mono ${jsonErr ? 'border-red-400' : ''}`}
        placeholder={placeholder || '{}'}
      />
      {jsonErr && <span className="text-xs text-red-500">{jsonErr}</span>}
    </div>
  );
}

function StepSpecDetails({ step, index, updateStep, executionType }) {
  const [open, setOpen] = useState(!!(step.step_type || step.tool_name || step.method || step.sql_script));
  const stepType = step.step_type || executionType || '';

  return (
    <div className="mt-2 border-t border-gray-200 pt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
      >
        <WrenchScrewdriverIcon className="w-3.5 h-3.5" />
        Spec Details
        <ChevronDownIcon className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="mt-2 space-y-2 p-2 bg-indigo-50/50 rounded-lg">
          {/* Step type selector */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium text-fg-mid">Step Type</label>
              <select
                value={step.step_type || ''}
                onChange={(e) => updateStep(index, 'step_type', e.target.value || null)}
                className="input-field text-xs"
              >
                {STEP_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-fg-mid">Connection Ref</label>
              <input
                value={step.connection_ref || ''}
                onChange={(e) => updateStep(index, 'connection_ref', e.target.value || null)}
                className="input-field text-xs"
                placeholder="e.g. reltio_mcp"
              />
            </div>
          </div>

          {/* MCP fields */}
          {(stepType === 'mcp') && (
            <div className="space-y-2">
              <div>
                <label className="text-xs font-medium text-fg-mid">Tool Name</label>
                <input
                  value={step.tool_name || ''}
                  onChange={(e) => updateStep(index, 'tool_name', e.target.value || null)}
                  className="input-field text-xs font-mono"
                  placeholder="e.g. health_check_tool"
                />
              </div>
              <JsonField
                label="Tool Parameters"
                value={step.tool_params}
                onChange={(v) => updateStep(index, 'tool_params', v)}
                placeholder='{"entity_type": "Individual", "max_results": 5}'
              />
            </div>
          )}

          {/* API fields */}
          {(stepType === 'api') && (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-xs font-medium text-fg-mid">Method</label>
                  <select
                    value={step.method || 'GET'}
                    onChange={(e) => updateStep(index, 'method', e.target.value)}
                    className="input-field text-xs"
                  >
                    {HTTP_METHODS.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-fg-mid">Endpoint</label>
                  <input
                    value={step.endpoint || ''}
                    onChange={(e) => updateStep(index, 'endpoint', e.target.value || null)}
                    className="input-field text-xs font-mono"
                    placeholder="/api/v1/entities"
                  />
                </div>
              </div>
              <JsonField
                label="Headers"
                value={step.headers}
                onChange={(v) => updateStep(index, 'headers', v)}
                rows={2}
                placeholder='{"Authorization": "Bearer ..."}'
              />
              <JsonField
                label="Request Body"
                value={step.request_body}
                onChange={(v) => updateStep(index, 'request_body', v)}
                placeholder='{"key": "value"}'
              />
            </div>
          )}

          {/* SQL fields */}
          {(stepType === 'sql') && (
            <div>
              <label className="text-xs font-medium text-fg-mid">SQL Script</label>
              <textarea
                value={step.sql_script || ''}
                onChange={(e) => updateStep(index, 'sql_script', e.target.value || null)}
                rows={4}
                className="input-field text-xs font-mono"
                placeholder="SELECT * FROM ..."
              />
            </div>
          )}

          {/* Assertions (all types) */}
          <JsonField
            label="Assertions"
            value={step.assertions}
            onChange={(v) => updateStep(index, 'assertions', v)}
            rows={3}
            placeholder={'[\n  {"type": "json_path", "path": "$.status", "expected": "ok"},\n  {"type": "not_empty"}\n]'}
          />
        </div>
      )}
    </div>
  );
}

export default function TestCaseEditor() {
  const { id: projectId, tcId } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [tc, setTc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Form fields
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [preconditions, setPreconditions] = useState('');
  const [expectedResult, setExpectedResult] = useState('');
  const [priority, setPriority] = useState('P2');
  const [category, setCategory] = useState('functional');
  const [status, setStatus] = useState('draft');
  const [executionType, setExecutionType] = useState('api');
  const [testSteps, setTestSteps] = useState([]);

  // Execution history
  const [executions, setExecutions] = useState([]);
  const [executionsLoading, setExecutionsLoading] = useState(true);
  const [expandedExec, setExpandedExec] = useState(null);
  const [selectedProof, setSelectedProof] = useState(null);

  const loadTestCase = useCallback(async () => {
    try {
      const res = await testCasesAPI.getById(projectId, tcId);
      const data = res.data;
      setTc(data);
      setTitle(data.title || '');
      setDescription(data.description || '');
      setPreconditions(data.preconditions || '');
      setExpectedResult(data.expected_result || '');
      setPriority(data.priority || 'P2');
      setCategory(data.category || 'functional');
      setStatus(data.status || 'draft');
      setExecutionType(data.execution_type || 'api');
      setTestSteps(data.test_steps || []);
    } catch (err) {
      setError('Failed to load test case.');
    } finally {
      setLoading(false);
    }
  }, [projectId, tcId]);

  const loadExecutions = useCallback(async () => {
    try {
      setExecutionsLoading(true);
      const res = await executionsAPI.list(projectId, { test_case_id: tcId });
      setExecutions(res.data || []);
    } catch {
      setExecutions([]);
    } finally {
      setExecutionsLoading(false);
    }
  }, [projectId, tcId]);

  useEffect(() => {
    loadTestCase();
    loadExecutions();
    projectsAPI.getById(projectId).then(res => setProject(res.data)).catch(() => {});
  }, [loadTestCase, loadExecutions, projectId]);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccessMsg('');
    try {
      const payload = {
        title,
        description: description || null,
        preconditions: preconditions || null,
        expected_result: expectedResult || null,
        priority,
        category,
        status,
        execution_type: executionType,
        test_steps: testSteps.map((s, i) => {
          const step = {
            step_number: i + 1,
            action: s.action || '',
            expected_result: s.expected_result || '',
          };
          // Preserve structured executable fields
          if (s.step_type) step.step_type = s.step_type;
          if (s.connection_ref) step.connection_ref = s.connection_ref;
          if (s.tool_name) step.tool_name = s.tool_name;
          if (s.tool_params) step.tool_params = s.tool_params;
          if (s.method) step.method = s.method;
          if (s.endpoint) step.endpoint = s.endpoint;
          if (s.headers) step.headers = s.headers;
          if (s.request_body) step.request_body = s.request_body;
          if (s.sql_script) step.sql_script = s.sql_script;
          if (s.assertions) step.assertions = s.assertions;
          return step;
        }),
      };
      const res = await testCasesAPI.update(projectId, tcId, payload);
      setTc(res.data);
      setSuccessMsg('Test case saved successfully.');
      setTimeout(() => setSuccessMsg(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete test case ${tc?.test_case_id}? This cannot be undone.`)) return;
    try {
      await testCasesAPI.delete(projectId, tcId);
      navigate(`/projects/${projectId}`);
    } catch (err) {
      setError('Failed to delete test case.');
    }
  };

  const handleRate = async ({ rating, feedback_text }) => {
    try {
      const res = await testCasesAPI.rate(projectId, tcId, { rating, feedback_text });
      setTc(res.data);
    } catch (err) {
      { const d = err.response?.data?.detail; alert(typeof d === 'string' ? d : (err.message || 'Failed to submit rating.')); }
    }
  };

  // Step management
  const addStep = () => {
    setTestSteps([...testSteps, { step_number: testSteps.length + 1, action: '', expected_result: '' }]);
  };

  const removeStep = (index) => {
    setTestSteps(testSteps.filter((_, i) => i !== index));
  };

  const updateStep = (index, field, value) => {
    const updated = [...testSteps];
    updated[index] = { ...updated[index], [field]: value };
    setTestSteps(updated);
  };

  const moveStep = (index, direction) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= testSteps.length) return;
    const updated = [...testSteps];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    setTestSteps(updated);
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="flex items-center justify-center py-20">
          <svg className="animate-spin w-8 h-8 text-fg-teal" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
    );
  }

  if (!tc) {
    return (
      <div className="page-container">
        <div className="card-static p-8 text-center">
          <p className="text-fg-mid">{error || 'Test case not found.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container max-w-4xl">
      {/* Breadcrumb */}
      <Breadcrumb items={[
        { label: 'Projects', to: '/projects' },
        { label: project?.name || 'Project', to: `/projects/${projectId}?tab=test_cases` },
        { label: tc.test_case_id },
      ]} />

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-mono font-bold text-fg-tealDark">{tc.test_case_id}</span>
            {tc.source === 'ai_generated' && (
              <span className="badge badge-teal text-xs">AI Generated</span>
            )}
          </div>
          <h1 className="text-xl font-bold text-fg-navy">{tc.title}</h1>
        </div>
        <button
          onClick={handleDelete}
          className="btn-danger text-sm flex items-center gap-2"
        >
          <TrashIcon className="w-4 h-4" />
          Delete
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 animate-fade-in">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700 animate-fade-in">
          {successMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main form -- 2/3 width */}
        <div className="lg:col-span-2 space-y-5">
          <div className="card-static p-5">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">Details</h3>

            <div className="space-y-4">
              <div>
                <label className="label">Title</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} className="input-field" />
              </div>

              <div>
                <label className="label">Description</label>
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="input-field" />
              </div>

              <div>
                <label className="label">Preconditions</label>
                <textarea value={preconditions} onChange={(e) => setPreconditions(e.target.value)} rows={2} className="input-field" />
              </div>

              <div>
                <label className="label">Expected Result</label>
                <textarea value={expectedResult} onChange={(e) => setExpectedResult(e.target.value)} rows={2} className="input-field" />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="label">Execution Type</label>
                  <select value={executionType} onChange={(e) => setExecutionType(e.target.value)} className="input-field">
                    <option value="api">🌐 API</option>
                    <option value="mcp">🔌 MCP Tool</option>
                    <option value="ui">🖥️ UI (Playwright)</option>
                    <option value="sql">🗄️ SQL (Database)</option>
                    <option value="mdm">🏢 MDM</option>
                    <option value="manual">✋ Manual</option>
                  </select>
                </div>
                <div>
                  <label className="label">Priority</label>
                  <select value={priority} onChange={(e) => setPriority(e.target.value)} className="input-field">
                    <option value="P1">P1 - Critical</option>
                    <option value="P2">P2 - High</option>
                    <option value="P3">P3 - Medium</option>
                    <option value="P4">P4 - Low</option>
                  </select>
                </div>
                <div>
                  <label className="label">Category</label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className="input-field">
                    <option value="functional">Functional</option>
                    <option value="integration">Integration</option>
                    <option value="regression">Regression</option>
                    <option value="smoke">Smoke</option>
                    <option value="e2e">End-to-End</option>
                  </select>
                </div>
                <div>
                  <label className="label">Status</label>
                  <select value={status} onChange={(e) => setStatus(e.target.value)} className="input-field">
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="passed">Passed</option>
                    <option value="failed">Failed</option>
                    <option value="blocked">Blocked</option>
                    <option value="deprecated">Deprecated</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Test Steps */}
          <div className="card-static p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider">
                Test Steps ({testSteps.length})
              </h3>
              <button onClick={addStep} className="btn-ghost text-sm flex items-center gap-1">
                <PlusIcon className="w-4 h-4" />
                Add Step
              </button>
            </div>

            {testSteps.length === 0 ? (
              <p className="text-sm text-fg-mid text-center py-4">
                No test steps. Click "Add Step" to begin.
              </p>
            ) : (
              <div className="space-y-3">
                {testSteps.map((step, idx) => (
                  <div key={idx} className="flex gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className="flex flex-col items-center gap-1 flex-shrink-0 pt-1">
                      <span className="w-7 h-7 rounded-full bg-fg-teal text-white text-xs font-bold flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <button
                        onClick={() => moveStep(idx, -1)}
                        disabled={idx === 0}
                        className="text-gray-300 hover:text-fg-mid disabled:opacity-30"
                        title="Move up"
                      >
                        <ArrowsUpDownIcon className="w-3.5 h-3.5 rotate-180" />
                      </button>
                      <button
                        onClick={() => moveStep(idx, 1)}
                        disabled={idx === testSteps.length - 1}
                        className="text-gray-300 hover:text-fg-mid disabled:opacity-30"
                        title="Move down"
                      >
                        <ArrowsUpDownIcon className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="flex-1 space-y-2">
                      <div>
                        <label className="text-xs font-medium text-fg-mid">Action</label>
                        <textarea
                          value={step.action || ''}
                          onChange={(e) => updateStep(idx, 'action', e.target.value)}
                          rows={2}
                          className="input-field text-sm"
                          placeholder="What to do..."
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-fg-mid">Expected Result</label>
                        <textarea
                          value={step.expected_result || ''}
                          onChange={(e) => updateStep(idx, 'expected_result', e.target.value)}
                          rows={2}
                          className="input-field text-sm"
                          placeholder="What should happen..."
                        />
                      </div>
                      <StepSpecDetails
                        step={step}
                        index={idx}
                        updateStep={updateStep}
                        executionType={executionType}
                      />
                    </div>
                    <button
                      onClick={() => removeStep(idx)}
                      className="text-gray-300 hover:text-red-500 flex-shrink-0 mt-1"
                      title="Remove step"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Execution History */}
          <div className="card-static p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider flex items-center gap-2">
                <ClockIcon className="w-4 h-4" />
                Execution History ({executions.length})
              </h3>
            </div>

            {executionsLoading ? (
              <p className="text-sm text-fg-mid text-center py-4">Loading executions...</p>
            ) : executions.length === 0 ? (
              <p className="text-sm text-fg-mid text-center py-4">
                No executions yet. Run this test via an agent or test plan.
              </p>
            ) : (
              <div className="space-y-2">
                {executions.map((exec) => {
                  const isPassed = exec.status === 'passed';
                  const isExpanded = expandedExec === exec.id;
                  return (
                    <div key={exec.id} className="border border-gray-200 rounded-lg overflow-hidden">
                      {/* Execution row header */}
                      <button
                        onClick={() => setExpandedExec(isExpanded ? null : exec.id)}
                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left"
                      >
                        {isPassed ? (
                          <CheckCircleIcon className="w-5 h-5 text-green-500 flex-shrink-0" />
                        ) : (
                          <XCircleIcon className="w-5 h-5 text-red-500 flex-shrink-0" />
                        )}
                        <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                          isPassed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {exec.status}
                        </span>
                        {exec.duration_ms != null && (
                          <span className="text-xs text-fg-mid">{exec.duration_ms}ms</span>
                        )}
                        <span className="text-xs text-fg-mid ml-auto">
                          {exec.executed_at ? new Date(exec.executed_at).toLocaleString() : ''}
                        </span>
                        {(exec.proof_artifacts || []).length > 0 && (
                          <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded font-medium">
                            {exec.proof_artifacts.length} proof{exec.proof_artifacts.length > 1 ? 's' : ''}
                          </span>
                        )}
                        <ChevronDownIcon className={`w-4 h-4 text-fg-mid transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                      </button>

                      {/* Expanded detail */}
                      {isExpanded && (
                        <div className="px-4 pb-4 border-t border-gray-100 bg-gray-50/50">
                          {exec.actual_result && (
                            <div className="mt-3">
                              <span className="text-xs font-semibold text-fg-mid uppercase">Actual Result</span>
                              <p className="text-sm text-fg-dark mt-1">{exec.actual_result}</p>
                            </div>
                          )}
                          {exec.error_message && (
                            <div className="mt-3">
                              <span className="text-xs font-semibold text-red-600 uppercase">Error</span>
                              <pre className="text-xs text-red-700 bg-red-50 rounded p-2 mt-1 overflow-x-auto whitespace-pre-wrap">
                                {exec.error_message}
                              </pre>
                            </div>
                          )}

                          {/* Proof artifacts */}
                          {(exec.proof_artifacts || []).length > 0 && (
                            <div className="mt-3">
                              <span className="text-xs font-semibold text-fg-mid uppercase">Proof Artifacts</span>
                              <div className="flex flex-wrap gap-2 mt-2">
                                {exec.proof_artifacts.map((proof, pi) => (
                                  <button
                                    key={pi}
                                    onClick={() => setSelectedProof(proof)}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-lg hover:border-fg-teal hover:shadow-sm transition-all text-sm group"
                                  >
                                    <DocumentMagnifyingGlassIcon className="w-4 h-4 text-fg-mid group-hover:text-fg-teal" />
                                    <span className="text-xs font-medium bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">
                                      {proof.proof_type}
                                    </span>
                                    <span className="text-fg-dark">{proof.title || 'View'}</span>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {exec.review_status && (
                            <div className="mt-3 flex items-center gap-2">
                              <span className="text-xs font-semibold text-fg-mid uppercase">Review:</span>
                              <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                                exec.review_status === 'approved' ? 'bg-green-100 text-green-700' :
                                exec.review_status === 'rejected' ? 'bg-red-100 text-red-700' :
                                'bg-yellow-100 text-yellow-700'
                              }`}>
                                {exec.review_status}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Save/Cancel */}
          <div className="flex justify-end gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}`)}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>

        {/* Sidebar -- 1/3 width */}
        <div className="space-y-5">
          {/* Rating card */}
          <div className="card-static p-5">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Quality Rating</h3>
            <RatingWidget
              value={tc.rating || 0}
              onSubmit={handleRate}
              size="lg"
            />
          </div>

          {/* Metadata card */}
          <div className="card-static p-5">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Metadata</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-fg-mid">Source</span>
                <span className="font-medium text-fg-dark capitalize">{tc.source?.replace(/_/g, ' ')}</span>
              </div>
              {tc.generated_by_model && (
                <div className="flex justify-between">
                  <span className="text-fg-mid">Model</span>
                  <span className="font-medium text-fg-dark">{tc.generated_by_model}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-fg-mid">Created</span>
                <span className="font-medium text-fg-dark">
                  {tc.created_at ? new Date(tc.created_at).toLocaleDateString() : '--'}
                </span>
              </div>
              {tc.updated_at && (
                <div className="flex justify-between">
                  <span className="text-fg-mid">Updated</span>
                  <span className="font-medium text-fg-dark">
                    {new Date(tc.updated_at).toLocaleDateString()}
                  </span>
                </div>
              )}
              {tc.domain_tags && tc.domain_tags.length > 0 && (
                <div className="pt-2">
                  <span className="text-fg-mid text-xs">Tags</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {tc.domain_tags.map((tag, i) => (
                      <span key={i} className="badge badge-gray text-xs">{tag}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Proof Viewer Modal */}
      <ProofViewer
        proof={selectedProof}
        visible={!!selectedProof}
        onClose={() => setSelectedProof(null)}
      />
    </div>
  );
}

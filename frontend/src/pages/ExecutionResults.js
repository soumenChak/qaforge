import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { executionAPI, projectsAPI } from '../services/api';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ArrowPathIcon,
  StopIcon,
  PhotoIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

const STATUS_STYLES = {
  queued: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Queued' },
  running: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Running' },
  completed: { bg: 'bg-green-100', text: 'text-green-700', label: 'Completed' },
  failed: { bg: 'bg-red-100', text: 'text-red-700', label: 'Failed' },
  cancelled: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Cancelled' },
};

const TEMPLATE_STYLES = {
  api_smoke: { bg: 'bg-indigo-50 text-indigo-600', label: 'API Smoke' },
  api_crud: { bg: 'bg-indigo-50 text-indigo-600', label: 'API CRUD' },
  db_query: { bg: 'bg-amber-50 text-amber-600', label: 'DB Query' },
  db_reconciliation: { bg: 'bg-amber-50 text-amber-600', label: 'DB Recon' },
  ui_playwright: { bg: 'bg-purple-50 text-purple-600', label: 'Playwright' },
  sandbox: { bg: 'bg-gray-50 text-gray-600', label: 'Sandbox' },
  none: { bg: 'bg-gray-50 text-gray-500', label: 'None' },
};

export default function ExecutionResults() {
  const { id: projectId, runId } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [cancelling, setCancelling] = useState(false);
  const [expandAll, setExpandAll] = useState(false);

  // Use ref to track run status without re-creating intervals
  const runStatusRef = useRef(null);
  const pollInFlightRef = useRef(false);

  const loadRun = useCallback(async ({ silent = false } = {}) => {
    if (silent && pollInFlightRef.current) return; // skip if poll in-flight
    if (silent) pollInFlightRef.current = true;
    try {
      const res = await executionAPI.getById(runId);
      runStatusRef.current = res.data.status;
      setRun(res.data);
    } catch (err) {
      console.error('Failed to load execution run:', err);
    } finally {
      if (!silent) setLoading(false);
      if (silent) pollInFlightRef.current = false;
    }
  }, [runId]);

  const loadProject = useCallback(async () => {
    try {
      const res = await projectsAPI.getById(projectId);
      setProject(res.data);
    } catch (err) {
      console.error('Failed to load project:', err);
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
    loadRun();
  }, [loadProject, loadRun]);

  // Poll while running — stable interval that checks ref, not state
  useEffect(() => {
    const interval = setInterval(() => {
      const status = runStatusRef.current;
      if (status && ['queued', 'running'].includes(status)) {
        loadRun({ silent: true });
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [loadRun]);

  const toggleRow = (tcId) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(tcId)) next.delete(tcId);
      else next.add(tcId);
      return next;
    });
  };

  const handleExpandAll = () => {
    if (expandAll) {
      setExpandedRows(new Set());
    } else {
      const allIds = new Set(testResults.map(tr => tr.test_case_id));
      setExpandedRows(allIds);
    }
    setExpandAll(!expandAll);
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await executionAPI.cancel(runId);
      runStatusRef.current = 'cancelled'; // stop polling immediately
      loadRun();
    } catch (err) {
      console.error('Failed to cancel:', err);
    } finally {
      setCancelling(false);
    }
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

  if (!run) {
    return (
      <div className="page-container">
        <div className="card-static p-8 text-center">
          <p className="text-fg-mid">Execution run not found.</p>
        </div>
      </div>
    );
  }

  const results = run.results || {};
  const testResults = results.test_results || [];
  const summary = results.summary || {};
  const statusStyle = STATUS_STYLES[run.status] || STATUS_STYLES.queued;
  const isActive = ['queued', 'running'].includes(run.status);
  const elapsed = run.started_at
    ? ((run.completed_at ? new Date(run.completed_at) : new Date()) - new Date(run.started_at)) / 1000
    : 0;

  return (
    <div className="page-container">
      {/* Breadcrumb */}
      <div className="mb-4">
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          className="text-sm text-fg-mid hover:text-fg-dark inline-flex items-center gap-1"
        >
          &larr; Back to {project?.name || 'Project'}
        </button>
      </div>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-fg-navy">Execution Results</h1>
          <p className="text-sm text-fg-mid mt-1">
            Run ID: {run.id.slice(0, 8)}...
            {run.started_at && ` — Started ${new Date(run.started_at).toLocaleString()}`}
            {elapsed > 0 && ` — ${Math.round(elapsed)}s total`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isActive && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="btn-secondary flex items-center gap-2 text-sm text-red-600 border-red-200 hover:bg-red-50"
            >
              <StopIcon className="w-4 h-4" />
              {cancelling ? 'Cancelling...' : 'Cancel Run'}
            </button>
          )}
          {!isActive && (
            <button
              onClick={loadRun}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <ArrowPathIcon className="w-4 h-4" />
              Refresh
            </button>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div className="card-static p-4">
          <p className="text-xs text-fg-mid mb-1">Status</p>
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-semibold ${statusStyle.bg} ${statusStyle.text}`}>
            {isActive && (
              <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {statusStyle.label}
          </span>
        </div>
        <div className="card-static p-4">
          <p className="text-xs text-fg-mid mb-1">Total Tests</p>
          <p className="text-2xl font-bold text-fg-navy">{summary.total || testResults.length || 0}</p>
        </div>
        <div className="card-static p-4">
          <p className="text-xs text-fg-mid mb-1">Passed</p>
          <p className="text-2xl font-bold text-green-600">{summary.passed || 0}</p>
        </div>
        <div className="card-static p-4">
          <p className="text-xs text-fg-mid mb-1">Failed</p>
          <p className="text-2xl font-bold text-red-600">{(summary.failed || 0) + (summary.errored || 0)}</p>
        </div>
        <div className="card-static p-4">
          <p className="text-xs text-fg-mid mb-1">Pass Rate</p>
          <p className={`text-2xl font-bold ${
            (summary.pass_rate || 0) >= 70 ? 'text-green-600' :
            (summary.pass_rate || 0) >= 40 ? 'text-yellow-600' : 'text-red-600'
          }`}>
            {summary.pass_rate != null ? `${summary.pass_rate}%` : '—'}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      {isActive && summary.total > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between text-xs text-fg-mid mb-1">
            <span>Progress: {summary.completed || 0} / {summary.total}</span>
            <span>{elapsed > 0 ? `${Math.round(elapsed)}s elapsed` : ''}</span>
          </div>
          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-fg-teal rounded-full transition-all duration-500"
              style={{ width: `${((summary.completed || 0) / summary.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Results table */}
      {testResults.length > 0 ? (
        <div className="card-static overflow-hidden">
          {/* Expand/Collapse all */}
          <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
            <span className="text-xs font-semibold text-fg-mid uppercase tracking-wide">Test Results</span>
            <button
              onClick={handleExpandAll}
              className="text-xs text-fg-teal hover:text-fg-tealDark"
            >
              {expandAll ? 'Collapse All' : 'Expand All'}
            </button>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="w-8 px-4 py-3" />
                <th className="text-left px-4 py-3 font-semibold text-fg-mid">ID</th>
                <th className="text-left px-4 py-3 font-semibold text-fg-mid">Title</th>
                <th className="text-left px-4 py-3 font-semibold text-fg-mid">Status</th>
                <th className="text-left px-4 py-3 font-semibold text-fg-mid">Template</th>
                <th className="text-right px-4 py-3 font-semibold text-fg-mid">Duration</th>
              </tr>
            </thead>
            <tbody>
              {testResults.map((tr) => {
                const isExpanded = expandedRows.has(tr.test_case_id);
                const isPassed = tr.status === 'passed';
                const isError = tr.status === 'error';
                const tmpl = TEMPLATE_STYLES[tr.template_used] || TEMPLATE_STYLES.none;
                const hasScreenshot = tr.details?.screenshot || tr.details?.failure_screenshot;
                const consoleLogs = tr.details?.console_logs;

                return (
                  <React.Fragment key={tr.test_case_id}>
                    <tr
                      className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => toggleRow(tr.test_case_id)}
                    >
                      <td className="px-4 py-3">
                        {isExpanded
                          ? <ChevronDownIcon className="w-4 h-4 text-fg-mid" />
                          : <ChevronRightIcon className="w-4 h-4 text-fg-mid" />
                        }
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-fg-tealDark">
                        {tr.test_case_display_id}
                      </td>
                      <td className="px-4 py-3 text-fg-dark font-medium">
                        {tr.title}
                        {hasScreenshot && (
                          <PhotoIcon className="w-3.5 h-3.5 inline ml-2 text-purple-400" title="Has screenshot" />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                          isPassed ? 'bg-green-100 text-green-700' :
                          isError ? 'bg-orange-100 text-orange-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {isPassed
                            ? <CheckCircleIcon className="w-3.5 h-3.5" />
                            : <XCircleIcon className="w-3.5 h-3.5" />
                          }
                          {tr.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${tmpl.bg}`}>
                          {tmpl.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-fg-mid">
                        <ClockIcon className="w-3.5 h-3.5 inline mr-1" />
                        {tr.duration_seconds ? `${tr.duration_seconds}s` : '—'}
                      </td>
                    </tr>

                    {/* Expanded row detail */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={6} className="px-8 py-4 bg-gray-50 border-b border-gray-200">
                          {/* Assertions */}
                          {tr.assertions && tr.assertions.length > 0 && (
                            <div className="mb-4">
                              <h4 className="text-xs font-bold text-fg-navy mb-2 uppercase tracking-wide">
                                Assertions ({tr.assertions.filter(a => a.passed).length}/{tr.assertions.length} passed)
                              </h4>
                              <div className="space-y-1">
                                {tr.assertions.map((a, idx) => (
                                  <div key={idx} className="flex items-center gap-2 text-xs">
                                    {a.passed
                                      ? <CheckCircleIcon className="w-4 h-4 text-green-500 flex-shrink-0" />
                                      : <XCircleIcon className="w-4 h-4 text-red-500 flex-shrink-0" />
                                    }
                                    <span className="text-fg-dark font-medium">{a.type}</span>
                                    {a.step && <span className="text-fg-mid">({a.step})</span>}
                                    {a.field && (
                                      <span className="text-fg-mid">field: <code className="bg-white px-1 rounded">{a.field}</code></span>
                                    )}
                                    {a.expected !== undefined && (
                                      <span className="text-fg-mid">
                                        expected: <code className="bg-white px-1 rounded">{JSON.stringify(a.expected)}</code>
                                      </span>
                                    )}
                                    {a.actual !== undefined && (
                                      <span className="text-fg-mid">
                                        actual: <code className={`px-1 rounded ${a.passed ? 'bg-green-50' : 'bg-red-50'}`}>{JSON.stringify(a.actual)}</code>
                                      </span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Execution Logs */}
                          {tr.logs && tr.logs.length > 0 && (
                            <div className="mb-4">
                              <h4 className="text-xs font-bold text-fg-navy mb-2 uppercase tracking-wide flex items-center gap-1">
                                <CommandLineIcon className="w-3.5 h-3.5" />
                                Execution Logs
                              </h4>
                              <pre className="bg-gray-900 text-gray-100 text-xs p-3 rounded-lg overflow-x-auto max-h-64 font-mono leading-relaxed">
                                {tr.logs.join('\n')}
                              </pre>
                            </div>
                          )}

                          {/* Response Preview (API tests) */}
                          {tr.details?.response_preview && (
                            <div className="mb-4">
                              <h4 className="text-xs font-bold text-fg-navy mb-2 uppercase tracking-wide">Response Preview</h4>
                              <pre className="bg-white border border-gray-200 text-xs p-3 rounded-lg overflow-x-auto max-h-32 font-mono text-fg-dark">
                                {tr.details.response_preview}
                              </pre>
                            </div>
                          )}

                          {/* Screenshot (Playwright UI tests) */}
                          {(tr.details?.screenshot || tr.details?.failure_screenshot) && (
                            <div className="mb-4">
                              <h4 className="text-xs font-bold text-fg-navy mb-2 uppercase tracking-wide flex items-center gap-1">
                                <PhotoIcon className="w-3.5 h-3.5" />
                                {tr.details?.failure_screenshot ? 'Failure Screenshot' : 'Screenshot'}
                              </h4>
                              <img
                                src={`data:image/png;base64,${tr.details?.failure_screenshot || tr.details?.screenshot}`}
                                alt="Test screenshot"
                                className="max-w-full rounded-lg border border-gray-200 shadow-sm"
                                style={{ maxHeight: '400px' }}
                              />
                            </div>
                          )}

                          {/* Console Logs (Playwright UI tests) */}
                          {consoleLogs && consoleLogs.length > 0 && (
                            <div className="mb-4">
                              <h4 className="text-xs font-bold text-fg-navy mb-2 uppercase tracking-wide">Browser Console</h4>
                              <pre className="bg-gray-800 text-gray-200 text-xs p-3 rounded-lg overflow-x-auto max-h-32 font-mono">
                                {consoleLogs.map((log, i) => (
                                  <span key={i} className={
                                    log.type === 'error' ? 'text-red-400' :
                                    log.type === 'warning' ? 'text-yellow-400' : 'text-gray-300'
                                  }>
                                    [{log.type}] {log.text}{'\n'}
                                  </span>
                                ))}
                              </pre>
                            </div>
                          )}

                          {/* SQL Results (DB tests) */}
                          {tr.details?.query_results && (
                            <div className="mb-4">
                              <h4 className="text-xs font-bold text-fg-navy mb-2 uppercase tracking-wide">Query Results</h4>
                              <pre className="bg-white border border-gray-200 text-xs p-3 rounded-lg overflow-x-auto max-h-40 font-mono text-fg-dark">
                                {JSON.stringify(tr.details.query_results, null, 2)}
                              </pre>
                            </div>
                          )}

                          {/* Step Details (CRUD / multi-step) */}
                          {tr.details?.steps && Object.keys(tr.details.steps).length > 0 && (
                            <div className="mb-4">
                              <h4 className="text-xs font-bold text-fg-navy mb-2 uppercase tracking-wide">Step Details</h4>
                              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                                {Object.entries(tr.details.steps).map(([step, info]) => (
                                  <div key={step} className="p-2 bg-white rounded border border-gray-200">
                                    <span className="text-xs font-semibold text-fg-dark capitalize">{step.replace(/_/g, ' ')}</span>
                                    <p className="text-xs text-fg-mid mt-0.5">
                                      Status: {typeof info === 'object' ? info.status || JSON.stringify(info) : info}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Duration */}
                          {tr.details?.total_duration_ms && (
                            <p className="text-xs text-fg-mid">
                              Total template duration: {tr.details.total_duration_ms}ms
                            </p>
                          )}

                          {/* Error */}
                          {tr.error && (
                            <div className="mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                              <strong>Error:</strong> {tr.error}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : isActive ? (
        <div className="card-static p-8 text-center">
          <svg className="animate-spin w-8 h-8 text-fg-teal mx-auto mb-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-fg-mid">Execution in progress... Results will appear here.</p>
        </div>
      ) : (
        <div className="card-static p-8 text-center">
          <p className="text-fg-mid">No test results available.</p>
        </div>
      )}
    </div>
  );
}

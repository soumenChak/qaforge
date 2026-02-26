import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectsAPI, requirementsAPI, testCasesAPI, executionAPI } from '../services/api';
import TestCaseTable from '../components/TestCaseTable';
import ExecutionRunModal from '../components/ExecutionRunModal';
import {
  SparklesIcon,
  PlusIcon,
  ArrowUpTrayIcon,
  DocumentMagnifyingGlassIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
  FunnelIcon,
  BoltIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  EyeIcon,
} from '@heroicons/react/24/outline';

const DOMAIN_COLORS = {
  mdm: 'bg-purple-100 text-purple-700',
  ai: 'bg-blue-100 text-blue-700',
  data_eng: 'bg-orange-100 text-orange-700',
};

const DOMAIN_NAMES = {
  mdm: 'MDM',
  ai: 'AI / GenAI',
  data_eng: 'Data Engineering',
};

const PRIORITY_COLORS = {
  high: 'badge-red',
  medium: 'badge-yellow',
  low: 'badge-green',
};

const RUN_STATUS_COLORS = {
  queued: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-yellow-100 text-yellow-700',
};

export default function ProjectDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [activeTab, setActiveTab] = useState('requirements');
  const [loading, setLoading] = useState(true);

  // Requirements state
  const [requirements, setRequirements] = useState([]);
  const [reqLoading, setReqLoading] = useState(false);
  const [showAddReq, setShowAddReq] = useState(false);
  const [newReq, setNewReq] = useState({ req_id: '', title: '', description: '', priority: 'medium', category: 'functional' });
  const [showUpload, setShowUpload] = useState(false);
  const [uploadText, setUploadText] = useState('');
  const [extracting, setExtracting] = useState(false);

  // Test cases state
  const [testCases, setTestCases] = useState([]);
  const [tcLoading, setTcLoading] = useState(false);
  const [selectedTcIds, setSelectedTcIds] = useState(new Set());
  const [tcFilter, setTcFilter] = useState({ status: '', priority: '', category: '', source: '' });
  const [tcPage, setTcPage] = useState(1);
  const [tcPageSize, setTcPageSize] = useState(25);
  const [tcTotal, setTcTotal] = useState(0);

  // Execution state
  const [showRunModal, setShowRunModal] = useState(false);
  const [executionRuns, setExecutionRuns] = useState([]);
  const [execLoading, setExecLoading] = useState(false);
  const executionRunsRef = useRef([]);

  const loadProject = useCallback(async () => {
    try {
      const res = await projectsAPI.getById(id);
      setProject(res.data);
    } catch (err) {
      console.error('Failed to load project:', err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadRequirements = useCallback(async () => {
    setReqLoading(true);
    try {
      const res = await requirementsAPI.list(id);
      setRequirements(res.data);
    } catch (err) {
      console.error('Failed to load requirements:', err);
    } finally {
      setReqLoading(false);
    }
  }, [id]);

  const loadTestCases = useCallback(async () => {
    setTcLoading(true);
    try {
      const params = {
        limit: tcPageSize,
        offset: (tcPage - 1) * tcPageSize,
      };
      if (tcFilter.status) params.status = tcFilter.status;
      if (tcFilter.priority) params.priority = tcFilter.priority;
      if (tcFilter.category) params.category = tcFilter.category;
      if (tcFilter.source) params.source = tcFilter.source;
      if (tcFilter.execution_type) params.execution_type = tcFilter.execution_type;

      const res = await testCasesAPI.list(id, params);
      setTestCases(res.data);
      setTcTotal(project?.test_case_count || res.data.length);
    } catch (err) {
      console.error('Failed to load test cases:', err);
    } finally {
      setTcLoading(false);
    }
  }, [id, tcPage, tcPageSize, tcFilter, project?.test_case_count]);

  const loadExecutionRuns = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setExecLoading(true);
    try {
      const res = await executionAPI.list({ project_id: id });
      setExecutionRuns(res.data);
      executionRunsRef.current = res.data;
    } catch (err) {
      console.error('Failed to load execution runs:', err);
    } finally {
      if (!silent) setExecLoading(false);
    }
  }, [id]);

  useEffect(() => { loadProject(); }, [loadProject]);
  useEffect(() => { if (activeTab === 'requirements') loadRequirements(); }, [activeTab, loadRequirements]);
  useEffect(() => { if (activeTab === 'test_cases') loadTestCases(); }, [activeTab, loadTestCases]);
  useEffect(() => { if (activeTab === 'executions') loadExecutionRuns(); }, [activeTab, loadExecutionRuns]);

  // Poll active runs — uses ref to avoid dependency on executionRuns state
  useEffect(() => {
    if (activeTab !== 'executions') return;
    const interval = setInterval(() => {
      const hasActive = executionRunsRef.current.some(r => ['queued', 'running'].includes(r.status));
      if (hasActive) loadExecutionRuns({ silent: true });
    }, 3000);
    return () => clearInterval(interval);
  }, [activeTab, loadExecutionRuns]);

  const handleAddRequirement = async (e) => {
    e.preventDefault();
    if (!newReq.req_id || !newReq.title) return;
    try {
      await requirementsAPI.create(id, newReq);
      setShowAddReq(false);
      setNewReq({ req_id: '', title: '', description: '', priority: 'medium', category: 'functional' });
      loadRequirements();
      loadProject();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to add requirement.');
    }
  };

  const handleExtract = async () => {
    if (!uploadText.trim()) return;
    setExtracting(true);
    try {
      await requirementsAPI.extract(id, {
        document_text: uploadText,
        document_type: 'brd',
        domain: project?.domain,
        sub_domain: project?.sub_domain,
      });
      setShowUpload(false);
      setUploadText('');
      loadRequirements();
      loadProject();
    } catch (err) {
      alert(err.response?.data?.detail || 'Extraction failed.');
    } finally {
      setExtracting(false);
    }
  };

  const handleDeleteReq = async (reqId, reqDisplayId) => {
    if (!window.confirm(`Delete requirement ${reqDisplayId}?`)) return;
    try {
      await requirementsAPI.delete(id, reqId);
      loadRequirements();
      loadProject();
    } catch (err) {
      alert('Failed to delete requirement.');
    }
  };

  const handleStatusChange = async (tc, newStatus) => {
    try {
      await testCasesAPI.update(id, tc.id, { status: newStatus });
      loadTestCases();
    } catch (err) {
      console.error('Failed to update status:', err);
    }
  };

  const handleExport = async () => {
    const ids = selectedTcIds.size > 0
      ? Array.from(selectedTcIds)
      : testCases.map((tc) => tc.id);
    if (ids.length === 0) return;

    try {
      const res = await testCasesAPI.exportExcel(id, {
        test_case_ids: ids,
        format: 'excel',
        include_steps: true,
        include_test_data: true,
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test_cases_${id}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Export failed.');
    }
  };

  const handleRunSelected = () => {
    if (selectedTcIds.size === 0) {
      alert('Please select test cases to run.');
      return;
    }
    setShowRunModal(true);
  };

  const handleRunAll = () => {
    // Select all test case IDs for execution
    const allIds = testCases.map(tc => tc.id);
    if (allIds.length === 0) {
      alert('No test cases available to run.');
      return;
    }
    setSelectedTcIds(new Set(allIds));
    setShowRunModal(true);
  };

  const handleExecutionStarted = (run) => {
    setShowRunModal(false);
    setActiveTab('executions');
    loadExecutionRuns();
  };

  if (loading || !project) {
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

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/projects')}
          className="text-sm text-fg-mid hover:text-fg-dark mb-3 inline-flex items-center gap-1"
        >
          &larr; Back to Projects
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-fg-navy">{project.name}</h1>
            <div className="flex items-center gap-2 mt-2">
              <span className={`badge ${DOMAIN_COLORS[project.domain] || 'badge-gray'}`}>
                {DOMAIN_NAMES[project.domain] || project.domain}
              </span>
              {project.sub_domain && (
                <span className="badge badge-gray">{project.sub_domain}</span>
              )}
              <span className={`badge ${
                project.status === 'active' ? 'badge-green' :
                project.status === 'completed' ? 'badge-teal' : 'badge-gray'
              }`}>
                {project.status}
              </span>
            </div>
          </div>

          <button
            onClick={() => navigate(`/projects/${id}/generate`)}
            className="btn-primary flex items-center gap-2"
          >
            <SparklesIcon className="w-4 h-4" />
            Generate Test Cases
          </button>
        </div>

        {project.description && (
          <p className="text-sm text-fg-mid mt-3 max-w-2xl">{project.description}</p>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 mb-6">
        {[
          { key: 'requirements', label: `Requirements (${requirements.length})` },
          { key: 'test_cases', label: `Test Cases (${project.test_case_count || 0})` },
          { key: 'executions', label: `Executions (${executionRuns.length})` },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors -mb-px
              ${activeTab === tab.key
                ? 'border-fg-teal text-fg-tealDark'
                : 'border-transparent text-fg-mid hover:text-fg-dark hover:border-gray-300'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Requirements tab */}
      {activeTab === 'requirements' && (
        <div className="animate-fade-in">
          {/* Actions */}
          <div className="flex flex-wrap gap-3 mb-5">
            <button
              onClick={() => {
                if (!showAddReq) {
                  const nextNum = requirements.length + 1;
                  setNewReq({ req_id: `REQ-${String(nextNum).padStart(3, '0')}`, title: '', description: '', priority: 'medium', category: 'functional' });
                }
                setShowAddReq(!showAddReq);
              }}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <PlusIcon className="w-4 h-4" />
              Add Requirement
            </button>
            <button
              onClick={() => setShowUpload(!showUpload)}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <ArrowUpTrayIcon className="w-4 h-4" />
              Upload BRD/PRD
            </button>
          </div>

          {/* Inline add form */}
          {showAddReq && (
            <div className="card-static p-5 mb-5 animate-slide-up">
              <form onSubmit={handleAddRequirement} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">REQ ID</label>
                  <input
                    value={newReq.req_id}
                    onChange={(e) => setNewReq({ ...newReq, req_id: e.target.value })}
                    placeholder="REQ-001"
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="label">Title</label>
                  <input
                    value={newReq.title}
                    onChange={(e) => setNewReq({ ...newReq, title: e.target.value })}
                    placeholder="Requirement title"
                    className="input-field"
                    autoFocus
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="label">Description</label>
                  <textarea
                    value={newReq.description}
                    onChange={(e) => setNewReq({ ...newReq, description: e.target.value })}
                    rows={2}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="label">Priority</label>
                  <select
                    value={newReq.priority}
                    onChange={(e) => setNewReq({ ...newReq, priority: e.target.value })}
                    className="input-field"
                  >
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div>
                  <label className="label">Category</label>
                  <input
                    value={newReq.category}
                    onChange={(e) => setNewReq({ ...newReq, category: e.target.value })}
                    placeholder="functional"
                    className="input-field"
                  />
                </div>
                <div className="sm:col-span-2 flex justify-end gap-3">
                  <button type="button" onClick={() => setShowAddReq(false)} className="btn-ghost text-sm">Cancel</button>
                  <button type="submit" className="btn-primary text-sm">Add Requirement</button>
                </div>
              </form>
            </div>
          )}

          {/* Upload/Extract panel */}
          {showUpload && (
            <div className="card-static p-5 mb-5 animate-slide-up">
              <h3 className="text-sm font-bold text-fg-navy mb-3">Upload BRD/PRD Text</h3>
              <textarea
                value={uploadText}
                onChange={(e) => setUploadText(e.target.value)}
                placeholder="Paste your BRD/PRD document text here..."
                rows={6}
                className="input-field mb-3"
              />
              <div className="flex justify-end gap-3">
                <button onClick={() => setShowUpload(false)} className="btn-ghost text-sm">Cancel</button>
                <button
                  onClick={handleExtract}
                  disabled={extracting || !uploadText.trim()}
                  className="btn-primary text-sm flex items-center gap-2"
                >
                  <DocumentMagnifyingGlassIcon className="w-4 h-4" />
                  {extracting ? 'Extracting...' : 'Extract Requirements'}
                </button>
              </div>
            </div>
          )}

          {/* Requirements list */}
          {reqLoading ? (
            <div className="text-center py-8 text-fg-mid">Loading requirements...</div>
          ) : requirements.length === 0 ? (
            <div className="card-static p-8 text-center">
              <p className="text-fg-mid">No requirements yet. Add manually or extract from a document.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {requirements.map((req) => (
                <div key={req.id} className="card-static p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono font-bold text-fg-tealDark">{req.req_id}</span>
                        <span className={`badge text-xs ${PRIORITY_COLORS[req.priority] || 'badge-gray'}`}>
                          {req.priority}
                        </span>
                        {req.category && <span className="badge badge-gray text-xs">{req.category}</span>}
                      </div>
                      <p className="text-sm font-medium text-fg-dark">{req.title}</p>
                      {req.description && (
                        <p className="text-xs text-fg-mid mt-1 line-clamp-2">{req.description}</p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteReq(req.id, req.req_id)}
                      className="text-gray-300 hover:text-red-500 ml-3 flex-shrink-0"
                      title="Delete requirement"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Test Cases tab */}
      {activeTab === 'test_cases' && (
        <div className="animate-fade-in">
          {/* Filters + actions */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
            <div className="flex flex-wrap items-center gap-3">
              <FunnelIcon className="w-4 h-4 text-fg-mid" />
              <select
                value={tcFilter.status}
                onChange={(e) => { setTcFilter({ ...tcFilter, status: e.target.value }); setTcPage(1); }}
                className="text-xs border rounded-md px-2 py-1.5 border-gray-200 focus:ring-fg-teal focus:border-fg-teal"
              >
                <option value="">All Status</option>
                {['draft', 'active', 'passed', 'failed', 'blocked'].map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
              <select
                value={tcFilter.priority}
                onChange={(e) => { setTcFilter({ ...tcFilter, priority: e.target.value }); setTcPage(1); }}
                className="text-xs border rounded-md px-2 py-1.5 border-gray-200 focus:ring-fg-teal focus:border-fg-teal"
              >
                <option value="">All Priority</option>
                {['P1', 'P2', 'P3', 'P4'].map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
              <select
                value={tcFilter.source}
                onChange={(e) => { setTcFilter({ ...tcFilter, source: e.target.value }); setTcPage(1); }}
                className="text-xs border rounded-md px-2 py-1.5 border-gray-200 focus:ring-fg-teal focus:border-fg-teal"
              >
                <option value="">All Sources</option>
                <option value="ai_generated">AI Generated</option>
                <option value="manual">Manual</option>
              </select>
              <select
                value={tcFilter.execution_type || ''}
                onChange={(e) => { setTcFilter({ ...tcFilter, execution_type: e.target.value }); setTcPage(1); }}
                className="text-xs border rounded-md px-2 py-1.5 border-gray-200 focus:ring-fg-teal focus:border-fg-teal"
              >
                <option value="">All Types</option>
                <option value="api">API</option>
                <option value="ui">UI (Playwright)</option>
                <option value="sql">SQL (Database)</option>
                <option value="manual">Manual</option>
              </select>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleRunSelected}
                disabled={selectedTcIds.size === 0}
                className="btn-secondary text-sm flex items-center gap-2 border-teal-200 text-teal-700 hover:bg-teal-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <BoltIcon className="w-4 h-4" />
                Run Selected ({selectedTcIds.size})
              </button>
              <button
                onClick={handleRunAll}
                disabled={testCases.length === 0}
                className="btn-secondary text-sm flex items-center gap-2"
              >
                <BoltIcon className="w-4 h-4" />
                Run All
              </button>
              <button
                onClick={handleExport}
                disabled={testCases.length === 0}
                className="btn-secondary text-sm flex items-center gap-2"
              >
                <ArrowDownTrayIcon className="w-4 h-4" />
                Export
              </button>
            </div>
          </div>

          <TestCaseTable
            testCases={testCases}
            loading={tcLoading}
            onRowClick={(tc) => navigate(`/projects/${id}/test-cases/${tc.id}`)}
            onStatusChange={handleStatusChange}
            selectedIds={selectedTcIds}
            onSelectChange={setSelectedTcIds}
            pagination={{
              page: tcPage,
              pageSize: tcPageSize,
              total: tcTotal,
              onPageChange: setTcPage,
              onPageSizeChange: (size) => { setTcPageSize(size); setTcPage(1); },
            }}
          />
        </div>
      )}

      {/* Executions tab */}
      {activeTab === 'executions' && (
        <div className="animate-fade-in">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
            <p className="text-sm text-fg-mid">
              {executionRuns.length} execution run{executionRuns.length !== 1 ? 's' : ''}
            </p>
            <button
              onClick={() => { setActiveTab('test_cases'); }}
              className="btn-secondary text-sm flex items-center gap-2"
            >
              <BoltIcon className="w-4 h-4" />
              Run New Execution
            </button>
          </div>

          {execLoading ? (
            <div className="text-center py-8 text-fg-mid">Loading execution runs...</div>
          ) : executionRuns.length === 0 ? (
            <div className="card-static p-8 text-center">
              <BoltIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-fg-mid mb-2">No execution runs yet.</p>
              <p className="text-xs text-fg-mid mb-4">
                Go to the Test Cases tab, select test cases, and click "Run Selected" to start.
              </p>
              <button
                onClick={() => setActiveTab('test_cases')}
                className="btn-primary text-sm"
              >
                Go to Test Cases
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {executionRuns.map((run) => {
                const summary = run.results?.summary || {};
                const isActive = ['queued', 'running'].includes(run.status);
                const passRate = summary.pass_rate;

                return (
                  <div
                    key={run.id}
                    className="card cursor-pointer overflow-hidden"
                    onClick={() => navigate(`/projects/${id}/executions/${run.id}`)}
                  >
                    <div className={`h-1 ${
                      run.status === 'completed' && (passRate || 0) >= 70 ? 'bg-gradient-to-r from-green-400 to-green-500' :
                      run.status === 'completed' ? 'bg-gradient-to-r from-orange-400 to-red-500' :
                      run.status === 'running' ? 'bg-gradient-to-r from-blue-400 to-blue-500' :
                      run.status === 'failed' ? 'bg-gradient-to-r from-red-400 to-red-500' :
                      'bg-gradient-to-r from-gray-300 to-gray-400'
                    }`} />

                    <div className="p-4 flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-4">
                        {/* Status badge */}
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${RUN_STATUS_COLORS[run.status] || 'bg-gray-100 text-gray-700'}`}>
                          {isActive && (
                            <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                          )}
                          {run.status}
                        </span>

                        {/* Test count */}
                        <span className="text-sm text-fg-dark">
                          {(run.test_case_ids || []).length} test case{(run.test_case_ids || []).length !== 1 ? 's' : ''}
                        </span>

                        {/* Results summary */}
                        {summary.passed !== undefined && (
                          <div className="flex items-center gap-3 text-xs">
                            <span className="flex items-center gap-1 text-green-600">
                              <CheckCircleIcon className="w-3.5 h-3.5" />
                              {summary.passed} passed
                            </span>
                            {(summary.failed || 0) + (summary.errored || 0) > 0 && (
                              <span className="flex items-center gap-1 text-red-600">
                                <XCircleIcon className="w-3.5 h-3.5" />
                                {(summary.failed || 0) + (summary.errored || 0)} failed
                              </span>
                            )}
                            {passRate != null && (
                              <span className={`font-semibold ${
                                passRate >= 70 ? 'text-green-600' :
                                passRate >= 40 ? 'text-yellow-600' : 'text-red-600'
                              }`}>
                                {passRate}% pass rate
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-4">
                        {/* Timestamp */}
                        <span className="text-xs text-gray-400 flex items-center gap-1">
                          <ClockIcon className="w-3.5 h-3.5" />
                          {run.started_at
                            ? new Date(run.started_at).toLocaleString()
                            : 'Queued'
                          }
                        </span>
                        <EyeIcon className="w-4 h-4 text-gray-400" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Execution Run Modal */}
      {showRunModal && (
        <ExecutionRunModal
          projectId={id}
          testCaseIds={Array.from(selectedTcIds)}
          testCaseCount={selectedTcIds.size}
          onClose={() => setShowRunModal(false)}
          onStarted={handleExecutionStarted}
        />
      )}
    </div>
  );
}

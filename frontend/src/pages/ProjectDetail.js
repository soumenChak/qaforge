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
  TrashIcon,
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

  // Add test case state
  const [showAddTc, setShowAddTc] = useState(false);
  const [newTc, setNewTc] = useState({
    test_case_id: '', title: '', description: '', preconditions: '',
    priority: 'P2', category: 'functional', execution_type: 'manual', expected_result: '',
    test_steps: [{ step_number: 1, action: '', expected_result: '' }],
  });

  // Bulk upload state
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  // Execution state
  const [showRunModal, setShowRunModal] = useState(false);
  const [executionRuns, setExecutionRuns] = useState([]);
  const [execLoading, setExecLoading] = useState(false);
  const executionRunsRef = useRef([]);

  // App Profile state
  const EMPTY_PROFILE = {
    app_url: '', api_base_url: '',
    tech_stack: { frontend: '', backend: '', database: '' },
    auth: { login_endpoint: '', request_body: '', token_header: '', test_credentials: { email: '', password: '' }, response_fields: [] },
    api_endpoints: [],
    ui_pages: [],
    rbac_model: '',
    notes: '',
  };
  const [appProfile, setAppProfile] = useState(EMPTY_PROFILE);
  const [appProfileDirty, setAppProfileDirty] = useState(false);
  const [appProfileSaving, setAppProfileSaving] = useState(false);
  const [appProfileMsg, setAppProfileMsg] = useState('');

  const loadProject = useCallback(async () => {
    try {
      const res = await projectsAPI.getById(id);
      setProject(res.data);
      // Load app profile (merge with defaults so all keys exist)
      if (res.data.app_profile) {
        setAppProfile(prev => {
          const merged = { ...prev, ...res.data.app_profile };
          merged.tech_stack = { ...prev.tech_stack, ...(res.data.app_profile.tech_stack || {}) };
          merged.auth = { ...prev.auth, ...(res.data.app_profile.auth || {}) };
          merged.auth.test_credentials = { ...prev.auth.test_credentials, ...(res.data.app_profile.auth?.test_credentials || {}) };
          merged.api_endpoints = res.data.app_profile.api_endpoints || [];
          merged.ui_pages = res.data.app_profile.ui_pages || [];
          return merged;
        });
      }
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
      const resp = await requirementsAPI.extract(id, {
        document_text: uploadText,
        document_type: 'brd',
        domain: project?.domain,
        sub_domain: project?.sub_domain,
      });
      const count = resp.data?.length || 0;
      setShowUpload(false);
      setUploadText('');
      loadRequirements();
      loadProject();
      if (count > 0) {
        alert(`✅ Successfully extracted ${count} requirements from your document using AI.`);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Extraction failed. Please try again.');
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

  const handleAddTestCase = async (e) => {
    e.preventDefault();
    if (!newTc.test_case_id || !newTc.title) return;
    try {
      const payload = {
        ...newTc,
        test_steps: newTc.test_steps.filter(s => s.action.trim()),
        source: 'manual',
      };
      if (payload.test_steps.length === 0) delete payload.test_steps;
      await testCasesAPI.create(id, payload);
      setShowAddTc(false);
      setNewTc({
        test_case_id: '', title: '', description: '', preconditions: '',
        priority: 'P2', category: 'functional', execution_type: 'manual', expected_result: '',
        test_steps: [{ step_number: 1, action: '', expected_result: '' }],
      });
      loadTestCases();
      loadProject();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to add test case.');
    }
  };

  const addStep = () => {
    setNewTc(prev => ({
      ...prev,
      test_steps: [...prev.test_steps, { step_number: prev.test_steps.length + 1, action: '', expected_result: '' }],
    }));
  };

  const removeStep = (idx) => {
    setNewTc(prev => ({
      ...prev,
      test_steps: prev.test_steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, step_number: i + 1 })),
    }));
  };

  const updateStep = (idx, field, value) => {
    setNewTc(prev => ({
      ...prev,
      test_steps: prev.test_steps.map((s, i) => i === idx ? { ...s, [field]: value } : s),
    }));
  };

  const handleDownloadTemplate = async () => {
    try {
      const res = await testCasesAPI.downloadTemplate(id);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test_case_template.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Failed to download template.');
    }
  };

  const handleBulkUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await testCasesAPI.bulkUpload(id, uploadFile);
      setUploadResult(res.data);
      if (res.data.created > 0) {
        loadTestCases();
        loadProject();
      }
    } catch (err) {
      setUploadResult({ error: err.response?.data?.detail || 'Upload failed.' });
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteTc = async (tc) => {
    if (!window.confirm(`Delete test case ${tc.test_case_id}: "${tc.title}"?`)) return;
    try {
      await testCasesAPI.delete(id, tc.id);
      loadTestCases();
      loadProject();
    } catch (err) {
      alert('Failed to delete test case.');
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedTcIds.size === 0) return;
    const count = selectedTcIds.size;
    if (!window.confirm(`Delete ${count} selected test case${count > 1 ? 's' : ''}? This cannot be undone.`)) return;
    try {
      const ids = Array.from(selectedTcIds);
      await Promise.all(ids.map((tcId) => testCasesAPI.delete(id, tcId)));
      setSelectedTcIds(new Set());
      loadTestCases();
      loadProject();
    } catch (err) {
      alert('Some test cases failed to delete.');
      loadTestCases();
      loadProject();
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
          { key: 'app_profile', label: `App Profile${appProfile.app_url || appProfile.api_base_url ? ' \u2713' : ''}` },
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
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-fg-navy">Upload BRD / PRD Document</h3>
                {uploadText.trim() && (
                  <span className="text-xs text-fg-mid">
                    {uploadText.length.toLocaleString()} chars
                    {uploadText.length > 30000 && ' — will be processed in multiple chunks'}
                  </span>
                )}
              </div>
              {/* Domain hint */}
              {project?.domain && (
                <div className="flex items-center gap-2 mb-3 p-2 bg-blue-50 rounded-lg">
                  <SparklesIcon className="w-4 h-4 text-blue-600 flex-shrink-0" />
                  <span className="text-xs text-blue-700">
                    AI will extract <strong>{project.domain === 'mdm' ? 'MDM-specific' : project.domain === 'ai' ? 'AI/GenAI-specific' : project.domain === 'data_eng' ? 'Data Engineering-specific' : 'domain-specific'}</strong> testable requirements using Sonnet — including data quality rules, integration points, edge cases, and acceptance criteria.
                  </span>
                </div>
              )}
              <textarea
                value={uploadText}
                onChange={(e) => setUploadText(e.target.value)}
                placeholder={project?.domain === 'mdm'
                  ? 'Paste your BRD/PRD here... The AI will extract MDM requirements including match/merge rules, data quality checks, survivorship logic, integration specs, and stewardship workflows.'
                  : project?.domain === 'ai'
                  ? 'Paste your BRD/PRD here... The AI will extract AI/GenAI requirements including model validation, prompt engineering, RAG pipeline, safety guardrails, and evaluation criteria.'
                  : project?.domain === 'data_eng'
                  ? 'Paste your BRD/PRD here... The AI will extract Data Engineering requirements including pipeline specs, data quality rules, orchestration, schema management, and SLA definitions.'
                  : 'Paste your BRD/PRD document text here... The AI will extract testable requirements with priority, category, and acceptance criteria.'}
                rows={10}
                className="input-field mb-3 font-mono text-xs"
              />
              <div className="flex items-center justify-between">
                <div className="text-xs text-fg-mid">
                  💡 Tip: Paste the entire document — longer docs produce better requirements. Headings and sections are preserved for traceability.
                </div>
                <div className="flex gap-3">
                  <button onClick={() => { setShowUpload(false); setUploadText(''); }} className="btn-ghost text-sm">Cancel</button>
                  <button
                    onClick={handleExtract}
                    disabled={extracting || !uploadText.trim()}
                    className="btn-primary text-sm flex items-center gap-2"
                  >
                    <DocumentMagnifyingGlassIcon className="w-4 h-4" />
                    {extracting ? (
                      <>
                        <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                        Extracting with AI...
                      </>
                    ) : `Extract Requirements${uploadText.trim() ? ` (${Math.ceil(uploadText.length / 1000)}K chars)` : ''}`}
                  </button>
                </div>
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
          {/* Action buttons row */}
          <div className="flex flex-wrap gap-3 mb-4">
            <button
              onClick={() => {
                if (!showAddTc) {
                  const nextNum = testCases.length + 1;
                  setNewTc(prev => ({
                    ...prev,
                    test_case_id: `TC-${String(nextNum).padStart(3, '0')}`,
                  }));
                }
                setShowAddTc(!showAddTc);
                setShowBulkUpload(false);
              }}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <PlusIcon className="w-4 h-4" />
              Add Test Case
            </button>
            <button
              onClick={() => { setShowBulkUpload(!showBulkUpload); setShowAddTc(false); setUploadResult(null); setUploadFile(null); }}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <ArrowUpTrayIcon className="w-4 h-4" />
              Bulk Upload
            </button>
          </div>

          {/* Inline Add Test Case form */}
          {showAddTc && (
            <div className="card-static p-5 mb-5 animate-slide-up">
              <h3 className="text-sm font-bold text-fg-navy mb-3">Add Test Case</h3>
              <form onSubmit={handleAddTestCase} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="label">Test Case ID *</label>
                    <input
                      value={newTc.test_case_id}
                      onChange={(e) => setNewTc({ ...newTc, test_case_id: e.target.value })}
                      placeholder="TC-001"
                      className="input-field"
                      required
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="label">Title *</label>
                    <input
                      value={newTc.title}
                      onChange={(e) => setNewTc({ ...newTc, title: e.target.value })}
                      placeholder="Verify user login returns JWT token"
                      className="input-field"
                      autoFocus
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="label">Description</label>
                    <textarea
                      value={newTc.description}
                      onChange={(e) => setNewTc({ ...newTc, description: e.target.value })}
                      rows={2}
                      placeholder="What does this test validate?"
                      className="input-field"
                    />
                  </div>
                  <div>
                    <label className="label">Preconditions</label>
                    <textarea
                      value={newTc.preconditions}
                      onChange={(e) => setNewTc({ ...newTc, preconditions: e.target.value })}
                      rows={2}
                      placeholder="Setup required before running this test"
                      className="input-field"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="label">Priority</label>
                    <select
                      value={newTc.priority}
                      onChange={(e) => setNewTc({ ...newTc, priority: e.target.value })}
                      className="input-field"
                    >
                      <option value="P1">P1 — Critical</option>
                      <option value="P2">P2 — High</option>
                      <option value="P3">P3 — Medium</option>
                      <option value="P4">P4 — Low</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">Category</label>
                    <select
                      value={newTc.category}
                      onChange={(e) => setNewTc({ ...newTc, category: e.target.value })}
                      className="input-field"
                    >
                      <option value="functional">Functional</option>
                      <option value="integration">Integration</option>
                      <option value="regression">Regression</option>
                      <option value="smoke">Smoke</option>
                      <option value="e2e">E2E</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">Execution Type</label>
                    <select
                      value={newTc.execution_type}
                      onChange={(e) => setNewTc({ ...newTc, execution_type: e.target.value })}
                      className="input-field"
                    >
                      <option value="api">API</option>
                      <option value="ui">UI (Playwright)</option>
                      <option value="sql">SQL (Database)</option>
                      <option value="manual">Manual</option>
                    </select>
                  </div>
                </div>

                {/* Test Steps */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="label mb-0">Test Steps</label>
                    <button type="button" onClick={addStep} className="text-xs text-fg-teal hover:text-fg-tealDark font-medium">
                      + Add Step
                    </button>
                  </div>
                  <div className="space-y-2">
                    {newTc.test_steps.map((step, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="text-xs text-fg-mid font-mono mt-2 w-6 text-right flex-shrink-0">{idx + 1}.</span>
                        <input
                          value={step.action}
                          onChange={(e) => updateStep(idx, 'action', e.target.value)}
                          placeholder="Action (e.g. POST /api/login with credentials)"
                          className="input-field flex-1 text-sm"
                        />
                        <span className="text-xs text-fg-mid mt-2 flex-shrink-0">&rarr;</span>
                        <input
                          value={step.expected_result}
                          onChange={(e) => updateStep(idx, 'expected_result', e.target.value)}
                          placeholder="Expected result"
                          className="input-field flex-1 text-sm"
                        />
                        {newTc.test_steps.length > 1 && (
                          <button type="button" onClick={() => removeStep(idx)} className="text-gray-300 hover:text-red-500 mt-2">
                            <XMarkIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="label">Expected Result</label>
                  <input
                    value={newTc.expected_result}
                    onChange={(e) => setNewTc({ ...newTc, expected_result: e.target.value })}
                    placeholder="Overall expected outcome"
                    className="input-field"
                  />
                </div>

                <div className="flex justify-end gap-3">
                  <button type="button" onClick={() => setShowAddTc(false)} className="btn-ghost text-sm">Cancel</button>
                  <button type="submit" className="btn-primary text-sm">Add Test Case</button>
                </div>
              </form>
            </div>
          )}

          {/* Bulk Upload panel */}
          {showBulkUpload && (
            <div className="card-static p-5 mb-5 animate-slide-up">
              <h3 className="text-sm font-bold text-fg-navy mb-3">Bulk Upload Test Cases</h3>
              <p className="text-xs text-fg-mid mb-4">
                Download the Excel template, fill in your test cases, then upload the completed file.
              </p>

              <div className="flex flex-wrap items-center gap-4 mb-4">
                <button
                  onClick={handleDownloadTemplate}
                  className="btn-secondary text-sm flex items-center gap-2"
                >
                  <ArrowDownTrayIcon className="w-4 h-4" />
                  Download Template
                </button>

                <div className="flex-1 min-w-[200px]">
                  <label className="flex items-center gap-3 px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-fg-teal hover:bg-teal-50/30 transition-colors">
                    <ArrowUpTrayIcon className="w-5 h-5 text-fg-mid" />
                    <span className="text-sm text-fg-mid">
                      {uploadFile ? uploadFile.name : 'Choose Excel file (.xlsx)'}
                    </span>
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      onChange={(e) => { setUploadFile(e.target.files[0] || null); setUploadResult(null); }}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>

              {/* Upload result */}
              {uploadResult && !uploadResult.error && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4 text-sm">
                  <p className="font-medium text-green-800">
                    Upload complete: {uploadResult.created} created, {uploadResult.skipped} skipped, {uploadResult.errors} errors
                  </p>
                  {uploadResult.errors > 0 && uploadResult.details?.errors?.length > 0 && (
                    <ul className="mt-2 text-xs text-red-600 space-y-1">
                      {uploadResult.details.errors.map((e, i) => (
                        <li key={i}>Row {e.row}: {e.error}</li>
                      ))}
                    </ul>
                  )}
                  {uploadResult.skipped > 0 && uploadResult.details?.skipped?.length > 0 && (
                    <ul className="mt-2 text-xs text-yellow-600 space-y-1">
                      {uploadResult.details.skipped.map((s, i) => (
                        <li key={i}>Row {s.row}: {s.tc_id} — {s.reason}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              {uploadResult?.error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm text-red-700">
                  {uploadResult.error}
                </div>
              )}

              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowBulkUpload(false); setUploadFile(null); setUploadResult(null); }} className="btn-ghost text-sm">Cancel</button>
                <button
                  onClick={handleBulkUpload}
                  disabled={!uploadFile || uploading}
                  className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50"
                >
                  <ArrowUpTrayIcon className="w-4 h-4" />
                  {uploading ? 'Uploading...' : 'Upload & Create'}
                </button>
              </div>
            </div>
          )}

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
              {selectedTcIds.size > 0 && (
                <button
                  onClick={handleDeleteSelected}
                  className="btn-secondary text-sm flex items-center gap-2 border-red-200 text-red-600 hover:bg-red-50"
                >
                  <TrashIcon className="w-4 h-4" />
                  Delete ({selectedTcIds.size})
                </button>
              )}
            </div>
          </div>

          <TestCaseTable
            testCases={testCases}
            loading={tcLoading}
            onRowClick={(tc) => navigate(`/projects/${id}/test-cases/${tc.id}`)}
            onStatusChange={handleStatusChange}
            onDelete={handleDeleteTc}
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

      {/* App Profile tab */}
      {activeTab === 'app_profile' && (
        <div className="animate-fade-in space-y-6 max-w-4xl">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="text-lg font-semibold text-fg-dark">Application Profile</h3>
              <p className="text-sm text-fg-mid mt-1">
                Provide details about the application under test. This information is injected into the AI prompt
                so generated test cases use <strong>exact URLs, endpoints, field names, and selectors</strong> instead of guessing.
              </p>
            </div>
            <button
              onClick={async () => {
                setAppProfileSaving(true);
                setAppProfileMsg('');
                try {
                  await projectsAPI.updateAppProfile(id, appProfile);
                  setAppProfileDirty(false);
                  setAppProfileMsg('Saved successfully');
                  setTimeout(() => setAppProfileMsg(''), 3000);
                } catch (err) {
                  setAppProfileMsg('Failed to save: ' + (err.response?.data?.detail || err.message));
                } finally {
                  setAppProfileSaving(false);
                }
              }}
              disabled={appProfileSaving || !appProfileDirty}
              className={`btn ${appProfileDirty ? 'btn-primary' : 'btn-secondary'} text-sm flex items-center gap-2`}
            >
              {appProfileSaving ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
          {appProfileMsg && (
            <div className={`text-sm px-3 py-2 rounded ${appProfileMsg.startsWith('Failed') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
              {appProfileMsg}
            </div>
          )}

          {/* URLs */}
          <div className="card p-5">
            <h4 className="text-sm font-semibold text-fg-dark mb-3">Target URLs</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-fg-mid mb-1">Application URL (for UI tests)</label>
                <input type="text" className="input w-full" placeholder="https://myapp.example.com"
                  value={appProfile.app_url} onChange={e => { setAppProfile(p => ({...p, app_url: e.target.value})); setAppProfileDirty(true); }} />
              </div>
              <div>
                <label className="block text-xs text-fg-mid mb-1">API Base URL (for API tests)</label>
                <input type="text" className="input w-full" placeholder="https://myapp.example.com/api"
                  value={appProfile.api_base_url} onChange={e => { setAppProfile(p => ({...p, api_base_url: e.target.value})); setAppProfileDirty(true); }} />
              </div>
            </div>
          </div>

          {/* Tech Stack */}
          <div className="card p-5">
            <h4 className="text-sm font-semibold text-fg-dark mb-3">Tech Stack</h4>
            <div className="grid grid-cols-3 gap-4">
              {['frontend', 'backend', 'database'].map(field => (
                <div key={field}>
                  <label className="block text-xs text-fg-mid mb-1 capitalize">{field}</label>
                  <input type="text" className="input w-full" placeholder={field === 'frontend' ? 'React' : field === 'backend' ? 'FastAPI' : 'PostgreSQL'}
                    value={appProfile.tech_stack?.[field] || ''} onChange={e => {
                      setAppProfile(p => ({...p, tech_stack: {...p.tech_stack, [field]: e.target.value}}));
                      setAppProfileDirty(true);
                    }} />
                </div>
              ))}
            </div>
          </div>

          {/* Authentication */}
          <div className="card p-5">
            <h4 className="text-sm font-semibold text-fg-dark mb-3">Authentication</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-fg-mid mb-1">Login Endpoint</label>
                <input type="text" className="input w-full" placeholder="POST /api/auth/login"
                  value={appProfile.auth?.login_endpoint || ''} onChange={e => {
                    setAppProfile(p => ({...p, auth: {...p.auth, login_endpoint: e.target.value}}));
                    setAppProfileDirty(true);
                  }} />
              </div>
              <div>
                <label className="block text-xs text-fg-mid mb-1">Auth Header Format</label>
                <input type="text" className="input w-full" placeholder='Authorization: Bearer <access_token>'
                  value={appProfile.auth?.token_header || ''} onChange={e => {
                    setAppProfile(p => ({...p, auth: {...p.auth, token_header: e.target.value}}));
                    setAppProfileDirty(true);
                  }} />
              </div>
              <div>
                <label className="block text-xs text-fg-mid mb-1">Request Body Format</label>
                <input type="text" className="input w-full" placeholder='{"email": "...", "password": "..."}'
                  value={appProfile.auth?.request_body || ''} onChange={e => {
                    setAppProfile(p => ({...p, auth: {...p.auth, request_body: e.target.value}}));
                    setAppProfileDirty(true);
                  }} />
              </div>
              <div>
                <label className="block text-xs text-fg-mid mb-1">Login Response Fields (comma-separated)</label>
                <input type="text" className="input w-full" placeholder="access_token, token_type, user"
                  value={(appProfile.auth?.response_fields || []).join(', ')} onChange={e => {
                    setAppProfile(p => ({...p, auth: {...p.auth, response_fields: e.target.value.split(',').map(s => s.trim()).filter(Boolean)}}));
                    setAppProfileDirty(true);
                  }} />
              </div>
              <div>
                <label className="block text-xs text-fg-mid mb-1">Test Email</label>
                <input type="text" className="input w-full" placeholder="admin@example.com"
                  value={appProfile.auth?.test_credentials?.email || ''} onChange={e => {
                    setAppProfile(p => ({...p, auth: {...p.auth, test_credentials: {...(p.auth?.test_credentials || {}), email: e.target.value}}}));
                    setAppProfileDirty(true);
                  }} />
              </div>
              <div>
                <label className="block text-xs text-fg-mid mb-1">Test Password</label>
                <input type="password" className="input w-full" placeholder="test123"
                  value={appProfile.auth?.test_credentials?.password || ''} onChange={e => {
                    setAppProfile(p => ({...p, auth: {...p.auth, test_credentials: {...(p.auth?.test_credentials || {}), password: e.target.value}}}));
                    setAppProfileDirty(true);
                  }} />
              </div>
            </div>
          </div>

          {/* API Endpoints */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-fg-dark">API Endpoints</h4>
              <button onClick={() => {
                setAppProfile(p => ({...p, api_endpoints: [...p.api_endpoints, {method: 'GET', path: '', description: '', required_fields: [], response_fields: []}]}));
                setAppProfileDirty(true);
              }} className="btn btn-secondary text-xs">+ Add Endpoint</button>
            </div>
            {appProfile.api_endpoints.length === 0 && (
              <p className="text-sm text-fg-mid italic">No endpoints defined. Add API endpoints so test cases use correct paths and fields.</p>
            )}
            <div className="space-y-3">
              {appProfile.api_endpoints.map((ep, idx) => (
                <div key={idx} className="bg-gray-50 rounded p-3 grid grid-cols-12 gap-2 items-start">
                  <select className="input col-span-2 text-xs" value={ep.method} onChange={e => {
                    const eps = [...appProfile.api_endpoints]; eps[idx] = {...eps[idx], method: e.target.value};
                    setAppProfile(p => ({...p, api_endpoints: eps})); setAppProfileDirty(true);
                  }}>
                    {['GET','POST','PUT','PATCH','DELETE'].map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                  <input className="input col-span-3 text-xs" placeholder="/api/endpoint" value={ep.path} onChange={e => {
                    const eps = [...appProfile.api_endpoints]; eps[idx] = {...eps[idx], path: e.target.value};
                    setAppProfile(p => ({...p, api_endpoints: eps})); setAppProfileDirty(true);
                  }} />
                  <input className="input col-span-2 text-xs" placeholder="Description" value={ep.description || ''} onChange={e => {
                    const eps = [...appProfile.api_endpoints]; eps[idx] = {...eps[idx], description: e.target.value};
                    setAppProfile(p => ({...p, api_endpoints: eps})); setAppProfileDirty(true);
                  }} />
                  <input className="input col-span-2 text-xs" placeholder="Required fields" value={(ep.required_fields || []).join(', ')} onChange={e => {
                    const eps = [...appProfile.api_endpoints]; eps[idx] = {...eps[idx], required_fields: e.target.value.split(',').map(s => s.trim()).filter(Boolean)};
                    setAppProfile(p => ({...p, api_endpoints: eps})); setAppProfileDirty(true);
                  }} />
                  <input className="input col-span-2 text-xs" placeholder="Response fields" value={(ep.response_fields || []).join(', ')} onChange={e => {
                    const eps = [...appProfile.api_endpoints]; eps[idx] = {...eps[idx], response_fields: e.target.value.split(',').map(s => s.trim()).filter(Boolean)};
                    setAppProfile(p => ({...p, api_endpoints: eps})); setAppProfileDirty(true);
                  }} />
                  <button className="col-span-1 text-red-400 hover:text-red-600 text-xs p-1" onClick={() => {
                    setAppProfile(p => ({...p, api_endpoints: p.api_endpoints.filter((_,i) => i !== idx)}));
                    setAppProfileDirty(true);
                  }}>
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* UI Pages */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-fg-dark">UI Pages</h4>
              <button onClick={() => {
                setAppProfile(p => ({...p, ui_pages: [...p.ui_pages, {route: '', description: '', key_elements: []}]}));
                setAppProfileDirty(true);
              }} className="btn btn-secondary text-xs">+ Add Page</button>
            </div>
            {appProfile.ui_pages.length === 0 && (
              <p className="text-sm text-fg-mid italic">No pages defined. Add UI pages so test cases use correct routes and selectors.</p>
            )}
            <div className="space-y-3">
              {appProfile.ui_pages.map((pg, idx) => (
                <div key={idx} className="bg-gray-50 rounded p-3 grid grid-cols-12 gap-2 items-start">
                  <input className="input col-span-3 text-xs" placeholder="/login" value={pg.route} onChange={e => {
                    const pgs = [...appProfile.ui_pages]; pgs[idx] = {...pgs[idx], route: e.target.value};
                    setAppProfile(p => ({...p, ui_pages: pgs})); setAppProfileDirty(true);
                  }} />
                  <input className="input col-span-4 text-xs" placeholder="Description" value={pg.description || ''} onChange={e => {
                    const pgs = [...appProfile.ui_pages]; pgs[idx] = {...pgs[idx], description: e.target.value};
                    setAppProfile(p => ({...p, ui_pages: pgs})); setAppProfileDirty(true);
                  }} />
                  <input className="input col-span-4 text-xs" placeholder="Key selectors (comma-sep)" value={(pg.key_elements || []).join(', ')} onChange={e => {
                    const pgs = [...appProfile.ui_pages]; pgs[idx] = {...pgs[idx], key_elements: e.target.value.split(',').map(s => s.trim()).filter(Boolean)};
                    setAppProfile(p => ({...p, ui_pages: pgs})); setAppProfileDirty(true);
                  }} />
                  <button className="col-span-1 text-red-400 hover:text-red-600 text-xs p-1" onClick={() => {
                    setAppProfile(p => ({...p, ui_pages: p.ui_pages.filter((_,i) => i !== idx)}));
                    setAppProfileDirty(true);
                  }}>
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* RBAC & Notes */}
          <div className="card p-5">
            <h4 className="text-sm font-semibold text-fg-dark mb-3">Additional Context</h4>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-fg-mid mb-1">RBAC Model</label>
                <input type="text" className="input w-full" placeholder="e.g., Filtered-data: users see only their allowed data, no 403 responses"
                  value={appProfile.rbac_model} onChange={e => { setAppProfile(p => ({...p, rbac_model: e.target.value})); setAppProfileDirty(true); }} />
              </div>
              <div>
                <label className="block text-xs text-fg-mid mb-1">Important Notes (corrections, naming conventions, gotchas)</label>
                <textarea className="input w-full" rows={4}
                  placeholder="e.g., Uses pipeline_stage not stage. Dashboard endpoint is /api/dashboard/stats not /api/dashboard."
                  value={appProfile.notes} onChange={e => { setAppProfile(p => ({...p, notes: e.target.value})); setAppProfileDirty(true); }} />
              </div>
            </div>
          </div>
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

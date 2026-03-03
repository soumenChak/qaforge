import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectsAPI, requirementsAPI, testCasesAPI, testPlansAPI, agentKeyAPI } from '../services/api';
import TestCaseTable from '../components/TestCaseTable';
import { DOMAIN_COLORS, DOMAIN_NAMES } from '../constants/domains';
import Breadcrumb from '../components/Breadcrumb';
import {
  SparklesIcon,
  PlusIcon,
  ArrowUpTrayIcon,
  DocumentMagnifyingGlassIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
  FunnelIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  EyeIcon,
  TrashIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  PencilSquareIcon,
} from '@heroicons/react/24/outline';

const PRIORITY_COLORS = {
  high: 'badge-red',
  medium: 'badge-yellow',
  low: 'badge-green',
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
  const [extractMode, setExtractMode] = useState('file'); // 'file' | 'text'
  const [extractFile, setExtractFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

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

  // Test Plans state
  const [testPlans, setTestPlans] = useState([]);
  const [testPlansLoading, setTestPlansLoading] = useState(false);
  // Agent key state
  const [agentKeyVisible, setAgentKeyVisible] = useState(null);
  const [generatingKey, setGeneratingKey] = useState(false);

  // App Profile state
  const EMPTY_PROFILE = {
    app_url: '', api_base_url: '',
    tech_stack: { frontend: '', backend: '', database: '' },
    auth: { login_endpoint: '', request_body: '', token_header: '', test_credentials: { email: '', password: '' }, response_fields: [] },
    api_endpoints: [],
    ui_pages: [],
    connections: {},
    rbac_model: '',
    notes: '',
    // Domain-specific config
    mdm_config: { entity_types: [], source_systems: [], match_rules: '', survivorship_rules: '', crosswalk_model: '', data_quality_rules: '' },
    data_eng_config: { pipelines: [], source_systems: '', target_systems: '', transformation_rules: '', scheduling: '', data_quality_rules: '' },
    ai_config: { llm_models: '', prompt_templates: '', evaluation_criteria: '', guardrails: '', rag_config: '', agent_workflows: '' },
  };
  const [appProfile, setAppProfile] = useState(EMPTY_PROFILE);
  const [appProfileDirty, setAppProfileDirty] = useState(false);
  const [appProfileSaving, setAppProfileSaving] = useState(false);
  const [appProfileMsg, setAppProfileMsg] = useState('');

  // BRD/PRD context state
  const [brdPrdText, setBrdPrdText] = useState('');
  const [brdPrdEditing, setBrdPrdEditing] = useState(false);
  const [brdPrdSaving, setBrdPrdSaving] = useState(false);
  const [brdPrdExpanded, setBrdPrdExpanded] = useState(false);

  // Coverage score state (Feature 2)
  const [coverage, setCoverage] = useState(null);
  const [coverageLoading, setCoverageLoading] = useState(false);

  // Profile validation state (Feature 3)
  const [validationResult, setValidationResult] = useState(null);
  const [validating, setValidating] = useState(false);

  // OpenAPI discovery state (Feature 4)
  const [openapiUrl, setOpenapiUrl] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discoveryMsg, setDiscoveryMsg] = useState('');

  // AI UI Discovery state
  const [uiDiscoveryRoutes, setUiDiscoveryRoutes] = useState('');
  const [uiDiscoveryCrawl, setUiDiscoveryCrawl] = useState(false);
  const [uiDiscovering, setUiDiscovering] = useState(false);
  const [uiDiscoveryMsg, setUiDiscoveryMsg] = useState('');
  const [expandedPages, setExpandedPages] = useState(new Set());

  // Connection registry state
  const [connModalOpen, setConnModalOpen] = useState(false);
  const [editingConnKey, setEditingConnKey] = useState(null);
  const EMPTY_CONN = { type: 'mcp', transport: 'sse', server_url: '', base_url: '', description: '', setup_command: '', env_vars: [], auth_type: '' };
  const [connDraft, setConnDraft] = useState(EMPTY_CONN);

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
          merged.mdm_config = { ...prev.mdm_config, ...(res.data.app_profile.mdm_config || {}) };
          merged.data_eng_config = { ...prev.data_eng_config, ...(res.data.app_profile.data_eng_config || {}) };
          merged.ai_config = { ...prev.ai_config, ...(res.data.app_profile.ai_config || {}) };
          merged.connections = res.data.app_profile.connections || {};
          return merged;
        });
      }
      // Load BRD/PRD text
      if (res.data.brd_prd_text) {
        setBrdPrdText(res.data.brd_prd_text);
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

  const loadTestPlans = useCallback(async () => {
    setTestPlansLoading(true);
    try {
      const res = await testPlansAPI.list(id);
      setTestPlans(res.data);
    } catch (err) {
      console.error('Failed to load test plans:', err);
    } finally {
      setTestPlansLoading(false);
    }
  }, [id]);

  // Load coverage when switching to test_cases tab
  const loadCoverage = useCallback(async () => {
    setCoverageLoading(true);
    try {
      const res = await projectsAPI.getCoverage(id);
      setCoverage(res.data);
    } catch (err) {
      console.error('Failed to load coverage:', err);
    } finally {
      setCoverageLoading(false);
    }
  }, [id]);

  useEffect(() => { loadProject(); }, [loadProject]);
  useEffect(() => { if (activeTab === 'requirements') loadRequirements(); }, [activeTab, loadRequirements]);
  useEffect(() => { if (activeTab === 'test_cases') { loadTestCases(); loadCoverage(); } }, [activeTab, loadTestCases, loadCoverage]);
  useEffect(() => { if (activeTab === 'test_plans') loadTestPlans(); }, [activeTab, loadTestPlans]);

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

  // File upload extraction (Excel, PDF, Word)
  const handleFileExtract = async () => {
    if (!extractFile) return;
    setExtracting(true);
    try {
      const formData = new FormData();
      formData.append('file', extractFile);
      if (project?.domain) formData.append('domain', project.domain);
      if (project?.sub_domain) formData.append('sub_domain', project.sub_domain);
      const resp = await requirementsAPI.uploadFile(id, formData);
      const count = resp.data?.length || 0;
      setShowUpload(false);
      setExtractFile(null);
      loadRequirements();
      loadProject();
      if (count > 0) {
        alert(`✅ Successfully extracted ${count} requirements from "${extractFile.name}" using AI.`);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'File extraction failed. Please try again.');
    } finally {
      setExtracting(false);
    }
  };

  // Drag & drop handlers
  const handleDragEnter = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(true); };
  const handleDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); };
  const handleDragOver = (e) => { e.preventDefault(); e.stopPropagation(); };
  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) {
      const ext = file.name.split('.').pop().toLowerCase();
      if (['xlsx', 'pdf', 'docx'].includes(ext)) {
        setExtractFile(file);
      } else {
        alert('Unsupported file type. Please upload .xlsx, .pdf, or .docx files.');
      }
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

  const handleDuplicateTc = async (tc) => {
    try {
      const res = await testCasesAPI.duplicate(id, tc.id);
      loadTestCases();
      loadProject();
      // Navigate to the new test case editor
      navigate(`/projects/${id}/test-cases/${res.data.id}`);
    } catch (err) {
      alert('Failed to duplicate test case.');
    }
  };

  const handleDeleteTc = async (tc) => {
    if (!window.confirm(`Delete test case ${tc.test_case_id}: "${tc.title}"?`)) return;
    try {
      await testCasesAPI.delete(id, tc.id);
      // Optimistic: remove from local state instead of full reload
      setTestCases((prev) => prev.filter((t) => t.id !== tc.id));
      loadProject(); // refresh project-level test_case_count
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
      await testCasesAPI.bulkDelete(id, ids); // single request instead of N
      // Optimistic: remove from local state
      setTestCases((prev) => prev.filter((tc) => !selectedTcIds.has(tc.id)));
      setSelectedTcIds(new Set());
      loadProject();
    } catch (err) {
      alert('Some test cases failed to delete.');
      loadTestCases();
      loadProject();
    }
  };

  const handleGenerateAgentKey = async () => {
    if (!window.confirm('Generate a new agent API key? Any existing key will be revoked.')) return;
    setGeneratingKey(true);
    try {
      const res = await agentKeyAPI.generate(id);
      setAgentKeyVisible(res.data.api_key);
      loadProject();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to generate agent key');
    } finally {
      setGeneratingKey(false);
    }
  };

  const handleRevokeAgentKey = async () => {
    if (!window.confirm('Revoke the agent API key? Agents will no longer be able to submit results.')) return;
    try {
      await agentKeyAPI.revoke(id);
      setAgentKeyVisible(null);
      loadProject();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to revoke agent key');
    }
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
      {/* Breadcrumb + Header */}
      <div className="mb-6">
        <Breadcrumb items={[
          { label: 'Projects', to: '/projects' },
          { label: project.name },
        ]} />

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

          {/* Generate Test Cases button removed — no frontend page yet; use Agent API */}
        </div>

        {project.description && (
          <p className="text-sm text-fg-mid mt-3 max-w-2xl">{project.description}</p>
        )}

        {/* Discovery Status Badges */}
        {(appProfile.api_endpoints?.length > 0 || appProfile.ui_pages?.length > 0 || appProfile.api_base_url) && (
          <div className="flex flex-wrap items-center gap-2 mt-3">
            {appProfile.api_endpoints?.length > 0 && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-1.024a4.5 4.5 0 00-1.242-7.244l-4.5-4.5a4.5 4.5 0 00-6.364 6.364L4.34 8.342" />
                </svg>
                {appProfile.api_endpoints.length} API endpoint{appProfile.api_endpoints.length !== 1 ? 's' : ''} discovered
              </span>
            )}
            {appProfile.ui_pages?.length > 0 && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a9 9 0 11-18 0V5.25" />
                </svg>
                {appProfile.ui_pages.length} UI page{appProfile.ui_pages.length !== 1 ? 's' : ''} mapped
                {' '}({appProfile.ui_pages.reduce((sum, p) => sum + (p.interactions?.length || p.key_elements?.length || 0), 0)} elements)
              </span>
            )}
            {appProfile.api_base_url && appProfile.api_endpoints?.length === 0 && (
              <button
                onClick={() => setActiveTab('app_profile')}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-colors cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
                API URL set — run discovery to map endpoints
              </button>
            )}
          </div>
        )}
      </div>

      {/* BRD/PRD Context — collapsible card */}
      {(brdPrdText || brdPrdEditing) && (
        <div className="mb-6 bg-white border border-gray-200 rounded-lg shadow-sm">
          <button
            type="button"
            onClick={() => setBrdPrdExpanded(!brdPrdExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 rounded-lg transition-colors"
          >
            <div className="flex items-center gap-2">
              <DocumentTextIcon className="w-4 h-4 text-fg-teal" />
              <span className="text-sm font-semibold text-fg-dark">BRD / PRD Context</span>
              <span className="text-xs text-fg-mid">
                {brdPrdText ? `${brdPrdText.trim().split(/\s+/).length} words` : 'Empty'}
              </span>
            </div>
            {brdPrdExpanded
              ? <ChevronUpIcon className="w-4 h-4 text-fg-mid" />
              : <ChevronDownIcon className="w-4 h-4 text-fg-mid" />
            }
          </button>
          {brdPrdExpanded && (
            <div className="px-4 pb-4">
              {brdPrdEditing ? (
                <>
                  <textarea
                    value={brdPrdText}
                    onChange={(e) => setBrdPrdText(e.target.value)}
                    rows={10}
                    placeholder="Paste your BRD/PRD document content here..."
                    className="w-full text-sm border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-fg-teal focus:border-fg-teal font-mono"
                  />
                  <div className="flex items-center gap-2 mt-2">
                    <button
                      onClick={async () => {
                        setBrdPrdSaving(true);
                        try {
                          await projectsAPI.update(id, { brd_prd_text: brdPrdText.trim() || null });
                          setBrdPrdEditing(false);
                          loadProject();
                        } catch (err) {
                          console.error('Failed to save BRD/PRD:', err);
                        } finally {
                          setBrdPrdSaving(false);
                        }
                      }}
                      disabled={brdPrdSaving}
                      className="btn-primary text-xs px-3 py-1.5"
                    >
                      {brdPrdSaving ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      onClick={() => {
                        setBrdPrdText(project.brd_prd_text || '');
                        setBrdPrdEditing(false);
                      }}
                      className="text-xs text-fg-mid hover:text-fg-dark"
                    >
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <pre className="text-xs text-fg-dark whitespace-pre-wrap font-mono bg-gray-50 rounded-lg p-3 max-h-64 overflow-y-auto">
                    {brdPrdText}
                  </pre>
                  <button
                    onClick={() => setBrdPrdEditing(true)}
                    className="mt-2 text-xs text-fg-teal hover:text-fg-tealDark font-medium flex items-center gap-1"
                  >
                    <PencilSquareIcon className="w-3.5 h-3.5" /> Edit
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
      {!brdPrdText && !brdPrdEditing && (
        <div className="mb-6">
          <button
            onClick={() => { setBrdPrdEditing(true); setBrdPrdExpanded(true); }}
            className="text-xs text-fg-teal hover:text-fg-tealDark font-medium flex items-center gap-1"
          >
            <DocumentTextIcon className="w-3.5 h-3.5" /> Add BRD/PRD Context
          </button>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 mb-6">
        {[
          { key: 'requirements', label: 'Requirements' },
          { key: 'test_cases', label: 'Test Cases' },
          { key: 'test_plans', label: 'Test Plans' },
          { key: 'app_profile', label: 'App Profile' },
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

          {/* Upload/Extract panel — dual mode: File Upload | Paste Text */}
          {showUpload && (
            <div className="card-static p-5 mb-5 animate-slide-up">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-fg-navy">Extract Requirements from BRD / PRD</h3>
                <button onClick={() => { setShowUpload(false); setUploadText(''); setExtractFile(null); }} className="text-fg-mid hover:text-fg-dark">
                  <XMarkIcon className="w-4 h-4" />
                </button>
              </div>

              {/* Mode toggle tabs */}
              <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
                <button
                  onClick={() => setExtractMode('file')}
                  className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${extractMode === 'file' ? 'bg-white text-fg-navy shadow-sm' : 'text-fg-mid hover:text-fg-dark'}`}
                >
                  <ArrowUpTrayIcon className="w-3.5 h-3.5 inline mr-1.5 -mt-0.5" />
                  Upload File
                </button>
                <button
                  onClick={() => setExtractMode('text')}
                  className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${extractMode === 'text' ? 'bg-white text-fg-navy shadow-sm' : 'text-fg-mid hover:text-fg-dark'}`}
                >
                  <DocumentTextIcon className="w-3.5 h-3.5 inline mr-1.5 -mt-0.5" />
                  Paste Text
                </button>
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

              {/* ── File Upload Mode ── */}
              {extractMode === 'file' && (
                <>
                  <div
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200
                      ${dragActive ? 'border-fg-teal bg-teal-50/50 scale-[1.01]' : 'border-gray-300 hover:border-fg-teal hover:bg-gray-50'}
                      ${extractFile ? 'border-green-400 bg-green-50/30' : ''}`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".xlsx,.pdf,.docx"
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) setExtractFile(f); e.target.value = ''; }}
                      className="hidden"
                    />
                    {extractFile ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                          {extractFile.name.endsWith('.xlsx') ? (
                            <span className="text-green-700 text-xs font-bold">XLS</span>
                          ) : extractFile.name.endsWith('.pdf') ? (
                            <span className="text-red-600 text-xs font-bold">PDF</span>
                          ) : (
                            <span className="text-blue-600 text-xs font-bold">DOC</span>
                          )}
                        </div>
                        <div className="text-left">
                          <p className="text-sm font-semibold text-fg-dark">{extractFile.name}</p>
                          <p className="text-xs text-fg-mid">{(extractFile.size / 1024).toFixed(1)} KB</p>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); setExtractFile(null); }}
                          className="ml-4 p-1 rounded hover:bg-red-100 text-fg-mid hover:text-red-600"
                        >
                          <XMarkIcon className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <ArrowUpTrayIcon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                        <p className="text-sm font-medium text-fg-dark mb-1">Drop your BRD/PRD file here</p>
                        <p className="text-xs text-fg-mid mb-3">or click to browse</p>
                        <div className="flex justify-center gap-2">
                          <span className="text-xxs px-2 py-0.5 rounded bg-green-100 text-green-700 font-medium">.xlsx</span>
                          <span className="text-xxs px-2 py-0.5 rounded bg-red-100 text-red-700 font-medium">.pdf</span>
                          <span className="text-xxs px-2 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">.docx</span>
                        </div>
                        <p className="text-xxs text-fg-mid mt-2">Max 10 MB</p>
                      </>
                    )}
                  </div>
                  <div className="flex items-center justify-between mt-4">
                    <div className="text-xs text-fg-mid">
                      Text is extracted from the file and processed by AI to identify requirements.
                    </div>
                    <div className="flex gap-3">
                      <button onClick={() => { setShowUpload(false); setExtractFile(null); }} className="btn-ghost text-sm">Cancel</button>
                      <button
                        onClick={handleFileExtract}
                        disabled={extracting || !extractFile}
                        className="btn-primary text-sm flex items-center gap-2"
                      >
                        <DocumentMagnifyingGlassIcon className="w-4 h-4" />
                        {extracting ? (
                          <>
                            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                            Extracting from file...
                          </>
                        ) : 'Extract Requirements'}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* ── Paste Text Mode ── */}
              {extractMode === 'text' && (
                <>
                  {uploadText.trim() && (
                    <div className="text-right mb-1">
                      <span className="text-xs text-fg-mid">
                        {uploadText.length.toLocaleString()} chars
                        {uploadText.length > 30000 && ' — will be processed in multiple chunks'}
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
                      Tip: Paste the entire document — longer docs produce better requirements.
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
                </>
              )}
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
          {/* Coverage Score Card (Feature 2) */}
          {coverage && coverage.total_requirements > 0 && (
            <div className="mb-4 card-static p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold text-white ${
                    coverage.grade === 'A' ? 'bg-green-500' :
                    coverage.grade === 'B' ? 'bg-blue-500' :
                    coverage.grade === 'C' ? 'bg-yellow-500' :
                    coverage.grade === 'D' ? 'bg-orange-500' : 'bg-red-500'
                  }`}>
                    {coverage.grade}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-fg-dark">
                      Test Coverage: {coverage.score}%
                    </p>
                    <p className="text-xs text-fg-mid">
                      {coverage.covered_requirements}/{coverage.total_requirements} requirements covered
                      {coverage.orphan_test_count > 0 && ` · ${coverage.orphan_test_count} unlinked tests`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {coverage.coverage_by_priority?.high && (
                    <span className="text-xs">
                      <span className="font-medium text-red-600">High:</span>{' '}
                      {coverage.coverage_by_priority.high.covered}/{coverage.coverage_by_priority.high.total}
                    </span>
                  )}
                  {coverage.coverage_by_priority?.medium && (
                    <span className="text-xs">
                      <span className="font-medium text-yellow-600">Med:</span>{' '}
                      {coverage.coverage_by_priority.medium.covered}/{coverage.coverage_by_priority.medium.total}
                    </span>
                  )}
                  {coverage.coverage_by_priority?.low && (
                    <span className="text-xs">
                      <span className="font-medium text-green-600">Low:</span>{' '}
                      {coverage.coverage_by_priority.low.covered}/{coverage.coverage_by_priority.low.total}
                    </span>
                  )}
                </div>
              </div>
              {/* Uncovered requirements */}
              {coverage.uncovered_details?.length > 0 && (
                <details className="mt-3">
                  <summary className="text-xs font-medium text-amber-700 cursor-pointer hover:text-amber-800">
                    {coverage.uncovered_requirements} uncovered requirement(s) — click to expand
                  </summary>
                  <div className="mt-2 space-y-1 pl-2 border-l-2 border-amber-200">
                    {coverage.uncovered_details.map((req, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          req.priority === 'high' ? 'bg-red-100 text-red-700' :
                          req.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-green-100 text-green-700'
                        }`}>{req.priority}</span>
                        <span className="font-mono text-fg-tealDark">{req.req_id}</span>
                        <span className="text-fg-dark">{req.title}</span>
                      </div>
                    ))}
                  </div>
                  {/* Generate Tests for Gaps button removed — no frontend page yet */}
                </details>
              )}
            </div>
          )}

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
            onDuplicate={handleDuplicateTc}
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

      {/* Test Plans tab */}
      {activeTab === 'test_plans' && (
        <div className="animate-fade-in">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
            <p className="text-sm text-fg-mid">
              {testPlans.length} test plan{testPlans.length !== 1 ? 's' : ''}
            </p>
            <button
              onClick={() => navigate(`/projects/${id}/test-plans`)}
              className="btn-primary text-sm flex items-center gap-2"
            >
              <DocumentTextIcon className="w-4 h-4" />
              Manage Test Plans
            </button>
          </div>

          {testPlansLoading ? (
            <div className="text-center py-8 text-fg-mid">Loading test plans...</div>
          ) : testPlans.length === 0 ? (
            <div className="card-static p-8 text-center">
              <DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-fg-mid mb-2">No test plans yet.</p>
              <p className="text-xs text-fg-mid mb-4">
                Create a test plan to organize test cases, track executions, and manage QA checkpoints.
              </p>
              <button
                onClick={() => navigate(`/projects/${id}/test-plans`)}
                className="btn-primary text-sm"
              >
                Create Test Plan
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {testPlans.map((plan) => {
                const passRate = plan.executed_count > 0
                  ? Math.round((plan.passed_count / plan.executed_count) * 100) : 0;
                return (
                  <div
                    key={plan.id}
                    className="card cursor-pointer overflow-hidden"
                    onClick={() => navigate(`/projects/${id}/test-plans/${plan.id}`)}
                  >
                    <div className={`h-1 ${
                      plan.status === 'completed' ? 'bg-gradient-to-r from-green-400 to-green-500' :
                      plan.status === 'active' ? 'bg-gradient-to-r from-blue-400 to-blue-500' :
                      plan.status === 'failed' ? 'bg-gradient-to-r from-red-400 to-red-500' :
                      'bg-gradient-to-r from-gray-300 to-gray-400'
                    }`} />
                    <div className="p-4 flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-4">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                          plan.status === 'completed' ? 'bg-green-100 text-green-700' :
                          plan.status === 'active' ? 'bg-blue-100 text-blue-700' :
                          plan.status === 'in_review' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {plan.status}
                        </span>
                        <span className="text-sm font-medium text-fg-dark">{plan.name}</span>
                        <span className="badge badge-gray text-xs">{plan.plan_type}</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>{plan.test_case_count} test cases</span>
                        <span>{plan.executed_count} executed</span>
                        {plan.executed_count > 0 && (
                          <span className={`font-semibold ${passRate >= 70 ? 'text-green-600' : passRate >= 40 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {passRate}% pass rate
                          </span>
                        )}
                        <span className="text-gray-400">
                          {new Date(plan.created_at).toLocaleDateString()}
                        </span>
                        <EyeIcon className="w-4 h-4 text-gray-400" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Agent API Key Section */}
          <div className="mt-8">
            <h3 className="text-lg font-semibold text-fg-dark mb-3">Agent API Key</h3>
            <p className="text-sm text-fg-mid mb-4">
              Generate an API key for AI agents (Claude Code, Codex, Gemini CLI) to submit test cases and execution results to this project.
            </p>
            <div className="card-static p-4">
              {agentKeyVisible ? (
                <div className="space-y-3">
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                    <p className="text-xs text-yellow-700 font-medium mb-1">Copy this key now — it won't be shown again.</p>
                    <code className="block text-sm bg-white rounded px-3 py-2 border font-mono break-all">{agentKeyVisible}</code>
                  </div>
                  <button onClick={() => { navigator.clipboard.writeText(agentKeyVisible); }} className="btn-secondary text-sm">
                    Copy to Clipboard
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  {project.has_agent_key ? (
                    <>
                      <span className="text-sm text-green-600 flex items-center gap-1">
                        <CheckCircleIcon className="w-4 h-4" /> Key active
                      </span>
                      <button onClick={handleRevokeAgentKey} className="btn-secondary text-sm text-red-600 border-red-200 hover:bg-red-50">
                        Revoke Key
                      </button>
                      <button onClick={handleGenerateAgentKey} disabled={generatingKey} className="btn-secondary text-sm">
                        {generatingKey ? 'Generating...' : 'Regenerate Key'}
                      </button>
                    </>
                  ) : (
                    <button onClick={handleGenerateAgentKey} disabled={generatingKey} className="btn-primary text-sm">
                      {generatingKey ? 'Generating...' : 'Generate Agent Key'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
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
            <div className="flex items-center gap-2">
              {/* Validate button (Feature 3) */}
              <button
                onClick={async () => {
                  setValidating(true);
                  setValidationResult(null);
                  try {
                    const res = await projectsAPI.validateProfile(id);
                    setValidationResult(res.data);
                  } catch (err) {
                    setValidationResult({ overall_status: 'fail', checks: [{ name: 'Error', status: 'fail', message: err.response?.data?.detail || err.message }] });
                  } finally {
                    setValidating(false);
                  }
                }}
                disabled={validating || appProfileDirty}
                className="btn btn-secondary text-sm flex items-center gap-2"
                title={appProfileDirty ? 'Save profile first' : 'Test endpoints against live app'}
              >
                {validating ? 'Validating...' : '✓ Validate'}
              </button>
              {/* Save button */}
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
          </div>
          {appProfileMsg && (
            <div className={`text-sm px-3 py-2 rounded ${appProfileMsg.startsWith('Failed') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
              {appProfileMsg}
            </div>
          )}

          {/* Validation Results (Feature 3) */}
          {validationResult && (
            <div className={`p-4 rounded-lg border ${
              validationResult.overall_status === 'pass' ? 'bg-green-50 border-green-200' :
              validationResult.overall_status === 'partial' ? 'bg-yellow-50 border-yellow-200' :
              'bg-red-50 border-red-200'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold">
                  Profile Validation: <span className={
                    validationResult.overall_status === 'pass' ? 'text-green-700' :
                    validationResult.overall_status === 'partial' ? 'text-yellow-700' : 'text-red-700'
                  }>{validationResult.overall_status.toUpperCase()}</span>
                </h4>
                <button onClick={() => setValidationResult(null)} className="text-xs text-fg-mid hover:text-fg-dark">✕</button>
              </div>
              <div className="space-y-1.5">
                {validationResult.checks?.map((check, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    {check.status === 'pass' ? (
                      <span className="w-5 h-5 rounded-full bg-green-500 text-white flex items-center justify-center text-[10px]">✓</span>
                    ) : check.status === 'fail' ? (
                      <span className="w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center text-[10px]">✕</span>
                    ) : check.status === 'warn' ? (
                      <span className="w-5 h-5 rounded-full bg-yellow-500 text-white flex items-center justify-center text-[10px]">!</span>
                    ) : (
                      <span className="w-5 h-5 rounded-full bg-gray-300 text-white flex items-center justify-center text-[10px]">—</span>
                    )}
                    <span className="font-medium text-fg-dark">{check.name}:</span>
                    <span className="text-fg-mid">{check.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* OpenAPI Auto-Discovery (Feature 4) */}
          <div className="card p-4">
            <h4 className="text-sm font-semibold text-fg-dark mb-2 flex items-center gap-2">
              <svg className="w-4 h-4 text-fg-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Auto-Discover from OpenAPI
            </h4>
            <p className="text-xs text-fg-mid mb-3">
              Paste your OpenAPI/Swagger URL to automatically populate API endpoints, auth schemes, and response fields.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                className="input flex-1"
                placeholder="https://myapp.example.com/api/openapi.json"
                value={openapiUrl}
                onChange={e => setOpenapiUrl(e.target.value)}
              />
              <button
                onClick={async () => {
                  if (!openapiUrl.trim()) return;
                  setDiscovering(true);
                  setDiscoveryMsg('');
                  try {
                    const res = await projectsAPI.discoverOpenAPI(id, { openapi_url: openapiUrl.trim() });
                    const newProfile = res.data.app_profile || {};
                    setAppProfile(prev => ({
                      ...prev,
                      ...newProfile,
                      tech_stack: { ...prev.tech_stack, ...(newProfile.tech_stack || {}) },
                      auth: { ...prev.auth, ...(newProfile.auth || {}) },
                    }));
                    const epCount = (newProfile.api_endpoints || []).length;
                    setDiscoveryMsg(`Discovered ${epCount} endpoint(s). Review and save.`);
                    setAppProfileDirty(true);
                  } catch (err) {
                    setDiscoveryMsg('Discovery failed: ' + (err.response?.data?.detail || err.message));
                  } finally {
                    setDiscovering(false);
                  }
                }}
                disabled={discovering || !openapiUrl.trim()}
                className="btn btn-primary text-sm px-4"
              >
                {discovering ? 'Discovering...' : 'Discover'}
              </button>
            </div>
            {discoveryMsg && (
              <p className={`text-xs mt-2 ${discoveryMsg.startsWith('Discovery failed') ? 'text-red-600' : 'text-green-600'}`}>
                {discoveryMsg}
              </p>
            )}
          </div>

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

          {/* AI UI Discovery */}
          <div className="card p-4">
            <h4 className="text-sm font-semibold text-fg-dark mb-2 flex items-center gap-2">
              <EyeIcon className="w-4 h-4 text-fg-teal" />
              AI-Powered UI Discovery
            </h4>
            <p className="text-xs text-fg-mid mb-3">
              Enter page routes and let the AI agent browse your app, take screenshots, and discover interactive elements with <strong>semantic locators</strong> (works on any app, including SaaS with dynamic CSS).
            </p>
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  className="input flex-1"
                  placeholder="/login, /dashboard, /entities, /settings"
                  value={uiDiscoveryRoutes}
                  onChange={e => setUiDiscoveryRoutes(e.target.value)}
                />
                <button
                  onClick={async () => {
                    const routes = uiDiscoveryRoutes.split(',').map(s => s.trim()).filter(Boolean);
                    if (routes.length === 0) return;
                    setUiDiscovering(true);
                    setUiDiscoveryMsg('');
                    try {
                      const res = await projectsAPI.discoverUI(id, { routes, crawl: uiDiscoveryCrawl, max_pages: 20 });
                      const newProfile = res.data.app_profile || {};
                      setAppProfile(prev => ({
                        ...prev,
                        ...newProfile,
                        tech_stack: { ...prev.tech_stack, ...(newProfile.tech_stack || {}) },
                        auth: { ...prev.auth, ...(newProfile.auth || {}) },
                        ui_pages: newProfile.ui_pages || prev.ui_pages,
                      }));
                      const pages = (newProfile.ui_pages || []);
                      const totalElems = pages.reduce((sum, p) => sum + (p.interactions || []).length, 0);
                      setUiDiscoveryMsg(`Discovered ${pages.length} page(s) with ${totalElems} interactive elements. Review below and save.`);
                      setAppProfileDirty(true);
                    } catch (err) {
                      setUiDiscoveryMsg('Discovery failed: ' + (err.response?.data?.detail || err.message));
                    } finally {
                      setUiDiscovering(false);
                    }
                  }}
                  disabled={uiDiscovering || !uiDiscoveryRoutes.trim() || !appProfile.app_url}
                  className="btn btn-primary text-sm px-4"
                >
                  {uiDiscovering ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                      Discovering...
                    </span>
                  ) : 'Discover UI'}
                </button>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-1.5 text-xs text-fg-mid cursor-pointer">
                  <input
                    type="checkbox"
                    checked={uiDiscoveryCrawl}
                    onChange={e => setUiDiscoveryCrawl(e.target.checked)}
                    className="rounded border-gray-300 text-fg-teal focus:ring-fg-teal"
                  />
                  Crawl mode (follow discovered navigation links)
                </label>
                {!appProfile.app_url && (
                  <span className="text-xs text-amber-600">Set Application URL above first</span>
                )}
              </div>
            </div>
            {uiDiscoveryMsg && (
              <p className={`text-xs mt-2 ${uiDiscoveryMsg.startsWith('Discovery failed') ? 'text-red-600' : 'text-green-600'}`}>
                {uiDiscoveryMsg}
              </p>
            )}
          </div>

          {/* UI Pages — Enhanced display with discovered elements */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-fg-dark">
                UI Pages
                {appProfile.ui_pages.length > 0 && (
                  <span className="ml-2 text-xs font-normal text-fg-mid">
                    ({appProfile.ui_pages.length} page{appProfile.ui_pages.length !== 1 ? 's' : ''},
                    {' '}{appProfile.ui_pages.reduce((sum, p) => sum + (p.interactions || []).length, 0)} elements)
                  </span>
                )}
              </h4>
              <button onClick={() => {
                setAppProfile(p => ({...p, ui_pages: [...p.ui_pages, {route: '', description: '', key_elements: []}]}));
                setAppProfileDirty(true);
              }} className="btn btn-secondary text-xs">+ Add Page</button>
            </div>
            {appProfile.ui_pages.length === 0 && (
              <p className="text-sm text-fg-mid italic">No pages discovered yet. Use AI Discovery above or add pages manually.</p>
            )}
            <div className="space-y-3">
              {appProfile.ui_pages.map((pg, idx) => {
                const hasDiscovery = (pg.interactions || []).length > 0;
                const isExpanded = expandedPages.has(idx);
                return (
                  <div key={idx} className={`rounded border ${hasDiscovery ? 'border-teal-200 bg-teal-50/30' : 'border-gray-200 bg-gray-50'}`}>
                    {/* Page header — always visible */}
                    <div className="p-3 flex items-center gap-2">
                      {hasDiscovery && (
                        <button
                          onClick={() => {
                            const next = new Set(expandedPages);
                            if (isExpanded) next.delete(idx); else next.add(idx);
                            setExpandedPages(next);
                          }}
                          className="text-fg-mid hover:text-fg-dark"
                        >
                          {isExpanded
                            ? <ChevronUpIcon className="w-4 h-4" />
                            : <ChevronDownIcon className="w-4 h-4" />
                          }
                        </button>
                      )}
                      <code className="text-xs font-mono font-semibold text-fg-tealDark bg-teal-100 px-1.5 py-0.5 rounded">
                        {pg.route || '(no route)'}
                      </code>
                      <span className="text-xs text-fg-mid flex-1 truncate">
                        {pg.purpose || pg.description || ''}
                      </span>
                      {hasDiscovery && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-teal-100 text-teal-700">
                          {pg.interactions.length} elements
                        </span>
                      )}
                      {(pg.forms || []).length > 0 && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">
                          {pg.forms.length} form{pg.forms.length !== 1 ? 's' : ''}
                        </span>
                      )}
                      {(pg.tables || []).length > 0 && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700">
                          {pg.tables.length} table{pg.tables.length !== 1 ? 's' : ''}
                        </span>
                      )}
                      <button className="text-red-400 hover:text-red-600 text-xs p-1" onClick={() => {
                        setAppProfile(p => ({...p, ui_pages: p.ui_pages.filter((_,i) => i !== idx)}));
                        setAppProfileDirty(true);
                      }}>
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Expanded: show discovered elements */}
                    {isExpanded && hasDiscovery && (
                      <div className="px-3 pb-3 border-t border-teal-200/50">
                        {/* Interactions grouped by category */}
                        <div className="mt-2 space-y-1">
                          <p className="text-[10px] font-semibold text-fg-mid uppercase tracking-wider">Interactive Elements</p>
                          {pg.interactions.map((elem, ei) => (
                            <div key={ei} className="flex items-start gap-2 text-xs pl-2">
                              <span className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                elem.category === 'button' ? 'bg-blue-400' :
                                elem.category === 'input' ? 'bg-green-400' :
                                elem.category === 'link' ? 'bg-purple-400' :
                                elem.category === 'dropdown' ? 'bg-orange-400' :
                                'bg-gray-400'
                              }`} />
                              <span className="font-medium text-fg-dark min-w-[100px]">{elem.element}</span>
                              <code className="text-[10px] font-mono text-teal-700 bg-teal-50 px-1 rounded flex-1 truncate">
                                {elem.locator}
                              </code>
                              {elem.purpose && (
                                <span className="text-fg-mid text-[10px] hidden lg:inline">{elem.purpose}</span>
                              )}
                            </div>
                          ))}
                        </div>

                        {/* Forms */}
                        {(pg.forms || []).length > 0 && (
                          <div className="mt-2">
                            <p className="text-[10px] font-semibold text-fg-mid uppercase tracking-wider">Forms</p>
                            {pg.forms.map((form, fi) => (
                              <div key={fi} className="text-xs pl-2 mt-1">
                                <span className="font-medium">{form.name}:</span>
                                <span className="text-fg-mid ml-1">{(form.fields || []).join(', ')}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Tables */}
                        {(pg.tables || []).length > 0 && (
                          <div className="mt-2">
                            <p className="text-[10px] font-semibold text-fg-mid uppercase tracking-wider">Tables</p>
                            {pg.tables.map((tbl, ti) => (
                              <div key={ti} className="text-xs pl-2 mt-1">
                                <span className="font-medium">{tbl.name}:</span>
                                <span className="text-fg-mid ml-1">{(tbl.columns || []).join(', ')}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Navigation */}
                        {(pg.navigation || []).length > 0 && (
                          <div className="mt-2">
                            <p className="text-[10px] font-semibold text-fg-mid uppercase tracking-wider">Navigation</p>
                            <p className="text-xs text-fg-mid pl-2">{pg.navigation.join(' | ')}</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* For non-discovered pages: editable fields */}
                    {!hasDiscovery && (
                      <div className="px-3 pb-3 grid grid-cols-12 gap-2">
                        <input className="input col-span-4 text-xs" placeholder="Route (/login)" value={pg.route} onChange={e => {
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
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Domain-Specific Config: MDM */}
          {project?.domain === 'mdm' && (
            <div className="card p-5">
              <div className="h-1 -mt-5 -mx-5 mb-4 bg-gradient-to-r from-purple-400 to-purple-600 rounded-t" />
              <h4 className="text-sm font-semibold text-fg-dark mb-1">MDM Configuration</h4>
              <p className="text-xs text-fg-mid mb-3">Reltio, Semarchy, or other MDM platform-specific settings that help generate accurate test cases.</p>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Entity Types (e.g., Person, Organization, Product — one per line)</label>
                  <textarea className="input w-full text-xs" rows={3}
                    placeholder={"Person (HCP)\nOrganization (HCO)\nProduct"}
                    value={(appProfile.mdm_config?.entity_types || []).join('\n')}
                    onChange={e => { setAppProfile(p => ({...p, mdm_config: {...(p.mdm_config || {}), entity_types: e.target.value.split('\n').filter(Boolean)}})); setAppProfileDirty(true); }}
                  />
                </div>
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Source Systems (e.g., CRM, ERP, MDH — one per line)</label>
                  <textarea className="input w-full text-xs" rows={2}
                    placeholder={"Salesforce CRM\nSAP ERP\nManual Entry"}
                    value={(appProfile.mdm_config?.source_systems || []).join('\n')}
                    onChange={e => { setAppProfile(p => ({...p, mdm_config: {...(p.mdm_config || {}), source_systems: e.target.value.split('\n').filter(Boolean)}})); setAppProfileDirty(true); }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Match Rules</label>
                    <textarea className="input w-full text-xs" rows={3}
                      placeholder="Exact match on Name+DOB, Fuzzy on Address, Probabilistic on Email"
                      value={appProfile.mdm_config?.match_rules || ''}
                      onChange={e => { setAppProfile(p => ({...p, mdm_config: {...(p.mdm_config || {}), match_rules: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Survivorship Rules</label>
                    <textarea className="input w-full text-xs" rows={3}
                      placeholder="Most recent wins for Phone, CRM wins for Email, Longest value for Name"
                      value={appProfile.mdm_config?.survivorship_rules || ''}
                      onChange={e => { setAppProfile(p => ({...p, mdm_config: {...(p.mdm_config || {}), survivorship_rules: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Crosswalk / Relationship Model</label>
                  <input type="text" className="input w-full text-xs"
                    placeholder="e.g., Crosswalks map source IDs to golden record URI, Relationships: HCP-affiliated-HCO"
                    value={appProfile.mdm_config?.crosswalk_model || ''}
                    onChange={e => { setAppProfile(p => ({...p, mdm_config: {...(p.mdm_config || {}), crosswalk_model: e.target.value}})); setAppProfileDirty(true); }}
                  />
                </div>
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Data Quality Rules</label>
                  <textarea className="input w-full text-xs" rows={2}
                    placeholder="Email format validation, Phone normalization, Address standardization, Required fields: Name, DOB"
                    value={appProfile.mdm_config?.data_quality_rules || ''}
                    onChange={e => { setAppProfile(p => ({...p, mdm_config: {...(p.mdm_config || {}), data_quality_rules: e.target.value}})); setAppProfileDirty(true); }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Domain-Specific Config: Data Engineering */}
          {project?.domain === 'data_eng' && (
            <div className="card p-5">
              <div className="h-1 -mt-5 -mx-5 mb-4 bg-gradient-to-r from-orange-400 to-orange-600 rounded-t" />
              <h4 className="text-sm font-semibold text-fg-dark mb-1">Data Engineering Configuration</h4>
              <p className="text-xs text-fg-mid mb-3">Pipeline, ETL/ELT, and data platform settings for targeted test generation.</p>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Pipelines (name, type — one per line)</label>
                  <textarea className="input w-full text-xs" rows={3}
                    placeholder={"orders_etl: Databricks Spark -> Delta Lake\ncustomer_sync: Kafka CDC -> Snowflake\ndaily_aggregation: dbt run"}
                    value={(appProfile.data_eng_config?.pipelines || []).join('\n')}
                    onChange={e => { setAppProfile(p => ({...p, data_eng_config: {...(p.data_eng_config || {}), pipelines: e.target.value.split('\n').filter(Boolean)}})); setAppProfileDirty(true); }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Source Systems</label>
                    <textarea className="input w-full text-xs" rows={2}
                      placeholder="PostgreSQL (OLTP), S3 bucket (raw landing), Kafka topics"
                      value={appProfile.data_eng_config?.source_systems || ''}
                      onChange={e => { setAppProfile(p => ({...p, data_eng_config: {...(p.data_eng_config || {}), source_systems: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Target Systems</label>
                    <textarea className="input w-full text-xs" rows={2}
                      placeholder="Snowflake (DWH), Delta Lake (curated layer), Redis (cache)"
                      value={appProfile.data_eng_config?.target_systems || ''}
                      onChange={e => { setAppProfile(p => ({...p, data_eng_config: {...(p.data_eng_config || {}), target_systems: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Transformation Rules</label>
                  <textarea className="input w-full text-xs" rows={3}
                    placeholder={"Medallion: Bronze (raw) -> Silver (cleansed) -> Gold (aggregated)\nKey transforms: date normalization, currency conversion, deduplication"}
                    value={appProfile.data_eng_config?.transformation_rules || ''}
                    onChange={e => { setAppProfile(p => ({...p, data_eng_config: {...(p.data_eng_config || {}), transformation_rules: e.target.value}})); setAppProfileDirty(true); }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Scheduling</label>
                    <input type="text" className="input w-full text-xs"
                      placeholder="Airflow DAG: daily at 02:00 UTC, Databricks job: hourly"
                      value={appProfile.data_eng_config?.scheduling || ''}
                      onChange={e => { setAppProfile(p => ({...p, data_eng_config: {...(p.data_eng_config || {}), scheduling: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Data Quality Rules</label>
                    <input type="text" className="input w-full text-xs"
                      placeholder="No nulls in key columns, row count variance < 5%, freshness < 24h"
                      value={appProfile.data_eng_config?.data_quality_rules || ''}
                      onChange={e => { setAppProfile(p => ({...p, data_eng_config: {...(p.data_eng_config || {}), data_quality_rules: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Domain-Specific Config: AI / GenAI */}
          {project?.domain === 'ai' && (
            <div className="card p-5">
              <div className="h-1 -mt-5 -mx-5 mb-4 bg-gradient-to-r from-blue-400 to-blue-600 rounded-t" />
              <h4 className="text-sm font-semibold text-fg-dark mb-1">AI / GenAI Configuration</h4>
              <p className="text-xs text-fg-mid mb-3">LLM, RAG, and agent-specific settings for testing AI-powered features.</p>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">LLM Models Used</label>
                    <input type="text" className="input w-full text-xs"
                      placeholder="GPT-4o, Claude 3.5 Sonnet, Llama 3.1"
                      value={appProfile.ai_config?.llm_models || ''}
                      onChange={e => { setAppProfile(p => ({...p, ai_config: {...(p.ai_config || {}), llm_models: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Evaluation Criteria</label>
                    <input type="text" className="input w-full text-xs"
                      placeholder="Accuracy, relevance, latency < 5s, no hallucinations"
                      value={appProfile.ai_config?.evaluation_criteria || ''}
                      onChange={e => { setAppProfile(p => ({...p, ai_config: {...(p.ai_config || {}), evaluation_criteria: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Prompt Templates / System Prompts</label>
                  <textarea className="input w-full text-xs" rows={3}
                    placeholder={"Chat: You are a helpful assistant for [domain]...\nRAG: Answer based on the provided context only..."}
                    value={appProfile.ai_config?.prompt_templates || ''}
                    onChange={e => { setAppProfile(p => ({...p, ai_config: {...(p.ai_config || {}), prompt_templates: e.target.value}})); setAppProfileDirty(true); }}
                  />
                </div>
                <div>
                  <label className="block text-xs text-fg-mid mb-1">Guardrails & Safety Rules</label>
                  <textarea className="input w-full text-xs" rows={2}
                    placeholder="Block PII in responses, refuse harmful content, no code execution, content moderation"
                    value={appProfile.ai_config?.guardrails || ''}
                    onChange={e => { setAppProfile(p => ({...p, ai_config: {...(p.ai_config || {}), guardrails: e.target.value}})); setAppProfileDirty(true); }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">RAG Configuration</label>
                    <textarea className="input w-full text-xs" rows={2}
                      placeholder="ChromaDB vector store, chunk_size=500, top_k=5, embedding=text-embedding-3-small"
                      value={appProfile.ai_config?.rag_config || ''}
                      onChange={e => { setAppProfile(p => ({...p, ai_config: {...(p.ai_config || {}), rag_config: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-fg-mid mb-1">Agent Workflows</label>
                    <textarea className="input w-full text-xs" rows={2}
                      placeholder="Multi-step: Planner -> Researcher -> Writer -> Reviewer, Tool-use: search, calculator"
                      value={appProfile.ai_config?.agent_workflows || ''}
                      onChange={e => { setAppProfile(p => ({...p, ai_config: {...(p.ai_config || {}), agent_workflows: e.target.value}})); setAppProfileDirty(true); }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Connections Registry ──────────────────────────────────── */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-sm font-semibold text-fg-dark">Connections Registry</h4>
                <p className="text-xs text-fg-mid mt-0.5">Named connections referenced by test steps via <code className="text-xs bg-gray-100 px-1 rounded">connection_ref</code>. Secrets are never stored — only env var names.</p>
              </div>
              <button
                onClick={() => {
                  setEditingConnKey(null);
                  setConnDraft({ ...EMPTY_CONN });
                  setConnModalOpen(true);
                }}
                className="btn btn-secondary text-xs flex items-center gap-1"
              >+ Add Connection</button>
            </div>

            {Object.keys(appProfile.connections || {}).length === 0 ? (
              <p className="text-xs text-fg-mid py-3 text-center">No connections configured yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-fg-mid">
                      <th className="py-2 pr-3 font-semibold">Name</th>
                      <th className="py-2 pr-3 font-semibold">Type</th>
                      <th className="py-2 pr-3 font-semibold">URL / Command</th>
                      <th className="py-2 pr-3 font-semibold">Description</th>
                      <th className="py-2 w-20"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(appProfile.connections).map(([key, conn]) => (
                      <tr key={key} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-2 pr-3 font-mono font-semibold text-indigo-700">{key}</td>
                        <td className="py-2 pr-3">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            conn.type === 'mcp' ? 'bg-purple-100 text-purple-700' :
                            conn.type === 'rest_api' ? 'bg-blue-100 text-blue-700' :
                            conn.type === 'database' ? 'bg-amber-100 text-amber-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>{conn.type}</span>
                        </td>
                        <td className="py-2 pr-3 font-mono text-fg-mid truncate max-w-[200px]">
                          {conn.server_url || conn.base_url || conn.setup_command || '—'}
                        </td>
                        <td className="py-2 pr-3 text-fg-mid truncate max-w-[200px]">{conn.description || '—'}</td>
                        <td className="py-2 flex gap-1">
                          <button
                            onClick={() => {
                              setEditingConnKey(key);
                              setConnDraft({ ...EMPTY_CONN, ...conn, _key: key });
                              setConnModalOpen(true);
                            }}
                            className="text-indigo-600 hover:text-indigo-800 font-medium"
                          >Edit</button>
                          <button
                            onClick={() => {
                              const conns = { ...appProfile.connections };
                              delete conns[key];
                              setAppProfile(p => ({ ...p, connections: conns }));
                              setAppProfileDirty(true);
                            }}
                            className="text-red-500 hover:text-red-700 font-medium ml-1"
                          >Del</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Connection Editor Modal */}
            {connModalOpen && (
              <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setConnModalOpen(false)}>
                <div className="bg-white rounded-lg shadow-xl p-5 w-full max-w-lg" onClick={e => e.stopPropagation()}>
                  <h4 className="text-sm font-semibold text-fg-dark mb-3">
                    {editingConnKey ? `Edit Connection: ${editingConnKey}` : 'Add Connection'}
                  </h4>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs text-fg-mid mb-1">Connection Name (key)</label>
                      <input
                        className="input w-full font-mono text-sm"
                        placeholder="e.g. reltio_mcp"
                        value={connDraft._key || ''}
                        onChange={e => setConnDraft(d => ({ ...d, _key: e.target.value.replace(/\s+/g, '_').toLowerCase() }))}
                        disabled={!!editingConnKey}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-fg-mid mb-1">Type</label>
                        <select className="input w-full text-sm" value={connDraft.type}
                          onChange={e => setConnDraft(d => ({ ...d, type: e.target.value }))}>
                          <option value="mcp">MCP Server</option>
                          <option value="rest_api">REST API</option>
                          <option value="database">Database</option>
                          <option value="grpc">gRPC</option>
                          <option value="other">Other</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-fg-mid mb-1">Transport</label>
                        <select className="input w-full text-sm" value={connDraft.transport || ''}
                          onChange={e => setConnDraft(d => ({ ...d, transport: e.target.value }))}>
                          <option value="">—</option>
                          <option value="sse">SSE</option>
                          <option value="stdio">stdio</option>
                          <option value="http">HTTP</option>
                          <option value="websocket">WebSocket</option>
                        </select>
                      </div>
                    </div>
                    {(connDraft.type === 'mcp') && (
                      <div>
                        <label className="block text-xs text-fg-mid mb-1">Server URL</label>
                        <input className="input w-full font-mono text-sm" placeholder="http://localhost:8000/sse"
                          value={connDraft.server_url || ''} onChange={e => setConnDraft(d => ({ ...d, server_url: e.target.value }))} />
                      </div>
                    )}
                    {(connDraft.type === 'rest_api' || connDraft.type === 'grpc') && (
                      <>
                        <div>
                          <label className="block text-xs text-fg-mid mb-1">Base URL</label>
                          <input className="input w-full font-mono text-sm" placeholder="https://api.example.com/v1"
                            value={connDraft.base_url || ''} onChange={e => setConnDraft(d => ({ ...d, base_url: e.target.value }))} />
                        </div>
                        <div>
                          <label className="block text-xs text-fg-mid mb-1">Auth Type</label>
                          <input className="input w-full text-sm" placeholder="e.g. oauth2, bearer, api_key"
                            value={connDraft.auth_type || ''} onChange={e => setConnDraft(d => ({ ...d, auth_type: e.target.value }))} />
                        </div>
                      </>
                    )}
                    {connDraft.type === 'database' && (
                      <div>
                        <label className="block text-xs text-fg-mid mb-1">Connection String Env Var</label>
                        <input className="input w-full font-mono text-sm" placeholder="DATABASE_URL"
                          value={connDraft.connection_string_env || ''} onChange={e => setConnDraft(d => ({ ...d, connection_string_env: e.target.value }))} />
                      </div>
                    )}
                    <div>
                      <label className="block text-xs text-fg-mid mb-1">Description</label>
                      <input className="input w-full text-sm" placeholder="What this connection is for"
                        value={connDraft.description || ''} onChange={e => setConnDraft(d => ({ ...d, description: e.target.value }))} />
                    </div>
                    <div>
                      <label className="block text-xs text-fg-mid mb-1">Setup Command (optional)</label>
                      <input className="input w-full font-mono text-sm" placeholder="cd /opt/mcp && python main.py"
                        value={connDraft.setup_command || ''} onChange={e => setConnDraft(d => ({ ...d, setup_command: e.target.value }))} />
                    </div>
                    <div>
                      <label className="block text-xs text-fg-mid mb-1">Required Env Vars (comma-separated names — secrets never stored)</label>
                      <input className="input w-full font-mono text-sm" placeholder="RELTIO_TENANT, RELTIO_CLIENT_ID, RELTIO_CLIENT_SECRET"
                        value={(connDraft.env_vars || []).join(', ')}
                        onChange={e => setConnDraft(d => ({ ...d, env_vars: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }))} />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 mt-4">
                    <button className="btn btn-secondary text-sm" onClick={() => setConnModalOpen(false)}>Cancel</button>
                    <button
                      className="btn btn-primary text-sm"
                      disabled={!connDraft._key}
                      onClick={() => {
                        const key = connDraft._key;
                        const { _key, ...connData } = connDraft;
                        // Remove empty fields
                        Object.keys(connData).forEach(k => { if (!connData[k] || (Array.isArray(connData[k]) && connData[k].length === 0)) delete connData[k]; });
                        // Preserve type always
                        connData.type = connDraft.type;
                        setAppProfile(p => ({
                          ...p,
                          connections: { ...(p.connections || {}), [key]: connData },
                        }));
                        setAppProfileDirty(true);
                        setConnModalOpen(false);
                      }}
                    >
                      {editingConnKey ? 'Update' : 'Add Connection'}
                    </button>
                  </div>
                </div>
              </div>
            )}
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

    </div>
  );
}

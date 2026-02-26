import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectsAPI, testCasesAPI, templatesAPI, knowledgeAPI, requirementsAPI } from '../services/api';
import ChatGenerator from '../components/ChatGenerator';
import {
  SparklesIcon,
  CheckCircleIcon,
  XCircleIcon,
  PencilSquareIcon,
  ArrowLeftIcon,
  ClockIcon,
  CpuChipIcon,
  BookOpenIcon,
  DocumentTextIcon,
  ClipboardDocumentListIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  LightBulbIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline';

const STEPS = [
  { key: 'describe', label: 'Describe' },
  { key: 'configure', label: 'Configure' },
  { key: 'generate', label: 'Generate' },
  { key: 'review', label: 'Review' },
];

export default function TestCaseGenerator() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);

  // Step 1: Description
  const [description, setDescription] = useState('');

  // Step 2: Configuration
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [count, setCount] = useState(10);
  const [additionalContext, setAdditionalContext] = useState('');
  const [priority, setPriority] = useState('');
  const [category, setCategory] = useState('');
  const [executionType, setExecutionType] = useState('');

  // Requirements context
  const [requirements, setRequirements] = useState([]);
  const [selectedReqIds, setSelectedReqIds] = useState(new Set());
  const [showReqPanel, setShowReqPanel] = useState(false);

  // BRD/PRD context
  const [brdPrdText, setBrdPrdText] = useState('');
  const [showBrdPanel, setShowBrdPanel] = useState(false);

  // Reference test cases
  const [existingTestCases, setExistingTestCases] = useState([]);
  const [selectedRefTcIds, setSelectedRefTcIds] = useState(new Set());
  const [showRefPanel, setShowRefPanel] = useState(false);

  // Knowledge Base context
  const [kbCount, setKbCount] = useState(0);
  const [kbEntries, setKbEntries] = useState([]);
  const [showKbPreview, setShowKbPreview] = useState(false);

  // Chat-based generation (Feature 6)
  const [showChat, setShowChat] = useState(false);

  // Step 3: Generation state
  const [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState('');

  // Step 4: Results
  const [results, setResults] = useState([]);
  const [resultMeta, setResultMeta] = useState(null);
  const [decisions, setDecisions] = useState({}); // id -> 'approve' | 'reject'

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

  useEffect(() => { loadProject(); }, [loadProject]);

  // Load templates
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const res = await templatesAPI.getAll();
        setTemplates(res.data);
      } catch (err) {
        // Templates are optional
      }
    };
    loadTemplates();
  }, []);

  // Load project requirements
  useEffect(() => {
    if (!id) return;
    const loadRequirements = async () => {
      try {
        const res = await requirementsAPI.list(id);
        setRequirements(res.data || []);
        // Auto-select all requirements by default
        if (res.data?.length > 0) {
          setSelectedReqIds(new Set(res.data.map((r) => r.id)));
        }
      } catch (err) {
        // Requirements are optional
      }
    };
    loadRequirements();
  }, [id]);

  // Load existing test cases (for reference selection)
  useEffect(() => {
    if (!id) return;
    const loadExistingTCs = async () => {
      try {
        const res = await testCasesAPI.list(id, { limit: 100 });
        setExistingTestCases(res.data || []);
      } catch (err) {
        // Reference TCs are optional
      }
    };
    loadExistingTCs();
  }, [id]);

  // Load KB entries count for the project's domain
  useEffect(() => {
    if (!project?.domain) return;
    const loadKbEntries = async () => {
      try {
        // Search with a broad term to get domain entries
        const res = await knowledgeAPI.search({ q: project.domain, domain: project.domain, limit: 10 });
        setKbEntries(res.data || []);
        setKbCount(res.data?.length || 0);
      } catch (err) {
        // Also try "general" entries
        try {
          const res2 = await knowledgeAPI.search({ q: 'test', limit: 10 });
          setKbEntries(res2.data || []);
          setKbCount(res2.data?.length || 0);
        } catch (err2) {
          // KB is optional
        }
      }
    };
    loadKbEntries();
  }, [project?.domain]);

  const handleGenerate = async () => {
    setStep(2);
    setGenerating(true);
    setGenerationError('');

    const startTime = Date.now();

    try {
      const reqIds = selectedReqIds.size > 0 ? Array.from(selectedReqIds) : null;
      const refTcIds = selectedRefTcIds.size > 0 ? Array.from(selectedRefTcIds) : null;

      const res = await testCasesAPI.generate(id, {
        description,
        domain: project?.domain,
        sub_domain: project?.sub_domain,
        count,
        additional_context: additionalContext || null,
        template_id: selectedTemplate || null,
        priority: priority || null,
        category: category || null,
        execution_type: executionType || null,
        requirement_ids: reqIds,
        brd_prd_text: brdPrdText.trim() || null,
        reference_test_case_ids: refTcIds,
      });

      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      setResults(res.data);
      setResultMeta({ duration: elapsed, count: res.data.length });

      // Default all to 'approve'
      const defaultDecisions = {};
      res.data.forEach((tc) => { defaultDecisions[tc.id] = 'approve'; });
      setDecisions(defaultDecisions);

      setStep(3);
    } catch (err) {
      setGenerationError(err.response?.data?.detail || 'Generation failed. Please try again.');
      setStep(1); // go back to configure
    } finally {
      setGenerating(false);
    }
  };

  const toggleReq = (reqId) => {
    const next = new Set(selectedReqIds);
    if (next.has(reqId)) next.delete(reqId);
    else next.add(reqId);
    setSelectedReqIds(next);
  };

  const toggleRefTc = (tcId) => {
    const next = new Set(selectedRefTcIds);
    if (next.has(tcId)) next.delete(tcId);
    else next.add(tcId);
    setSelectedRefTcIds(next);
  };

  // ── Smart Prompt Suggestion Builder ──
  const buildSuggestedPrompt = () => {
    if (!project) return null;

    const domain = project.domain;
    const subDomain = project.sub_domain || 'General';
    const projName = project.name;
    const projDesc = project.description || '';

    // Gather key requirements (high priority first)
    const highReqs = requirements.filter((r) => r.priority === 'high').slice(0, 5);
    const medReqs = requirements.filter((r) => r.priority === 'medium').slice(0, 3);
    const keyReqs = [...highReqs, ...medReqs];

    // Gather unique categories from existing TCs
    const existingCategories = [...new Set(existingTestCases.map((tc) => tc.category).filter(Boolean))];
    const existingExecTypes = [...new Set(existingTestCases.map((tc) => tc.execution_type).filter(Boolean))];

    // Build smart prompt
    let prompt = `Test the ${projName} system`;
    if (projDesc) {
      prompt += ` — ${projDesc.substring(0, 200)}`;
    }
    prompt += `.\n\n`;

    // Add domain-specific focus areas
    const domainFocus = {
      mdm: 'Focus on data quality, match/merge rules, survivorship logic, golden record integrity, cross-reference validation, and data stewardship workflows.',
      ai: 'Focus on model accuracy, prompt injection prevention, response validation, hallucination detection, latency testing, and API integration correctness.',
      data_eng: 'Focus on pipeline reliability, data freshness, schema evolution, ETL reconciliation, incremental loads, and data quality checks.',
      integration: 'Focus on API contract validation, event-driven flows, error handling, retry logic, idempotency, and end-to-end data flow integrity.',
      digital: 'Focus on user workflows, form validation, responsive behavior, authentication flows, error states, and cross-browser compatibility.',
    };
    if (domainFocus[domain]) {
      prompt += domainFocus[domain] + '\n\n';
    }

    // Add key requirements as bullet points
    if (keyReqs.length > 0) {
      prompt += 'Key requirements to cover:\n';
      keyReqs.forEach((r) => {
        prompt += `• ${r.title}${r.description ? ': ' + r.description.substring(0, 100) : ''}\n`;
      });
      prompt += '\n';
    }

    // Add guidance on what types to generate
    if (existingTestCases.length > 0) {
      prompt += `There are already ${existingTestCases.length} test cases`;
      if (existingCategories.length > 0) {
        prompt += ` covering ${existingCategories.join(', ')}`;
      }
      prompt += `. Generate NEW test cases for scenarios not yet covered — focus on edge cases, error handling, negative testing, and integration points.\n`;
    }

    // Add execution type hints
    if (existingExecTypes.length > 0) {
      prompt += `Include a mix of ${existingExecTypes.join(' and ')} test cases.`;
    }

    return prompt.trim();
  };

  const approvedCount = Object.values(decisions).filter((d) => d === 'approve').length;
  const rejectedCount = Object.values(decisions).filter((d) => d === 'reject').length;

  // Finalize: delete rejected TCs from DB, then navigate to project
  const [finalizing, setFinalizing] = useState(false);
  const handleFinalize = async () => {
    const rejectedIds = Object.entries(decisions)
      .filter(([, d]) => d === 'reject')
      .map(([tcId]) => tcId);

    if (rejectedIds.length > 0) {
      setFinalizing(true);
      try {
        await testCasesAPI.bulkDelete(id, rejectedIds);
      } catch (err) {
        console.error('Failed to delete rejected TCs:', err);
        // Still navigate even if delete fails
      }
      setFinalizing(false);
    }
    navigate(`/projects/${id}`);
  };

  // Count total context sources being used
  const contextSourceCount =
    (requirements.length > 0 ? 1 : 0) +
    (brdPrdText.trim() ? 1 : 0) +
    (selectedRefTcIds.size > 0 ? 1 : 0) +
    (kbCount > 0 ? 1 : 0);

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
    <div className="page-container max-w-4xl">
      {/* Back + header */}
      <button
        onClick={() => navigate(`/projects/${id}`)}
        className="text-sm text-fg-mid hover:text-fg-dark mb-4 inline-flex items-center gap-1"
      >
        <ArrowLeftIcon className="w-4 h-4" />
        Back to {project.name}
      </button>

      <h1 className="text-2xl font-bold text-fg-navy mb-2">Generate Test Cases</h1>
      <p className="text-sm text-fg-mid mb-8">
        {project.domain} / {project.sub_domain || 'General'}
      </p>

      {/* Step indicator */}
      <div className="flex items-center mb-8">
        {STEPS.map((s, i) => (
          <React.Fragment key={s.key}>
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                ${i <= step
                  ? 'bg-gradient-to-r from-fg-teal to-fg-green text-white'
                  : 'bg-gray-200 text-fg-mid'
                }`}>
                {i < step ? (
                  <CheckCircleIcon className="w-5 h-5" />
                ) : (
                  i + 1
                )}
              </div>
              <span className={`text-sm font-medium hidden sm:inline ${i <= step ? 'text-fg-dark' : 'text-fg-mid'}`}>
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mx-3 ${i < step ? 'bg-fg-teal' : 'bg-gray-200'}`} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Step 1: Describe */}
      {step === 0 && (
        <div className="card-static p-6 animate-fade-in">
          <h2 className="text-lg font-bold text-fg-navy mb-1">What do you want to test?</h2>
          <p className="text-sm text-fg-mid mb-4">
            Describe the system, feature, or workflow you need test cases for.
          </p>

          {/* Smart prompt suggestion */}
          {!description.trim() && (requirements.length > 0 || project?.description) && (
            <div className="mb-4 p-4 rounded-xl bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200">
              <div className="flex items-start gap-3">
                <LightBulbIcon className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-amber-900 mb-1">
                    Smart Prompt Available
                  </p>
                  <p className="text-xs text-amber-700 mb-3">
                    We can generate a prompt based on your project's {requirements.length > 0 ? `${requirements.length} requirements` : 'description'}
                    {existingTestCases.length > 0 ? ` and ${existingTestCases.length} existing test cases` : ''}.
                    This gives the AI the best context for quality test generation.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      const suggested = buildSuggestedPrompt();
                      if (suggested) setDescription(suggested);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg
                      bg-amber-100 hover:bg-amber-200 text-amber-800 transition-colors"
                  >
                    <SparklesIcon className="w-3.5 h-3.5" />
                    Use Suggested Prompt
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Context indicators */}
          {(requirements.length > 0 || existingTestCases.length > 0) && (
            <div className="flex flex-wrap gap-2 mb-3">
              {requirements.length > 0 && (
                <span className="badge text-xs bg-teal-100 text-teal-700">
                  📋 {requirements.length} requirements loaded
                </span>
              )}
              {existingTestCases.length > 0 && (
                <span className="badge text-xs bg-purple-100 text-purple-700">
                  📎 {existingTestCases.length} existing test cases
                </span>
              )}
              {kbCount > 0 && (
                <span className="badge text-xs bg-green-100 text-green-700">
                  📚 {kbCount} KB patterns
                </span>
              )}
            </div>
          )}

          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g., We have a Reltio MDM system that merges customer records using match rules. The golden record should merge name, address, and phone fields from multiple source systems (SAP, Salesforce, Oracle). Test the merge logic, survivorship rules, and data quality checks..."
            rows={8}
            className="input-field mb-4"
            autoFocus
          />
          <div className="flex justify-between items-center">
            <span className="text-xs text-fg-mid self-center">
              {description.length > 0 ? `${description.length} characters` : 'Start typing or use the smart prompt'}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowChat(true)}
                className="btn-secondary flex items-center gap-1.5"
                title="Chat with an AI agent that asks questions before generating"
              >
                <ChatBubbleLeftRightIcon className="w-4 h-4" />
                Chat with Agent
              </button>
              <button
                onClick={() => setStep(1)}
                disabled={!description.trim()}
                className="btn-primary"
              >
                Next: Configure
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Chat-based generation overlay (Feature 6) */}
      {showChat && (
        <ChatGenerator
          projectId={id}
          onGenerated={(tcs) => {
            setShowChat(false);
            navigate(`/projects/${id}?tab=test_cases`);
          }}
          onClose={() => setShowChat(false)}
        />
      )}

      {/* Step 2: Configure */}
      {step === 1 && (
        <div className="card-static p-6 animate-fade-in">
          <h2 className="text-lg font-bold text-fg-navy mb-4">Configure Generation</h2>

          {generationError && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              {generationError}
            </div>
          )}

          {/* Context sources summary */}
          {contextSourceCount > 0 && (
            <div className="mb-5 p-3 rounded-lg bg-gradient-to-r from-teal-50 to-green-50 border border-teal-200">
              <div className="flex items-center gap-2 text-sm text-teal-800 font-medium">
                <SparklesIcon className="w-4 h-4 text-teal-600" />
                Generation will use {contextSourceCount} context {contextSourceCount === 1 ? 'source' : 'sources'}:
                <span className="flex gap-1 flex-wrap">
                  {requirements.length > 0 && (
                    <span className="badge text-xs bg-teal-100 text-teal-700">{selectedReqIds.size} requirements</span>
                  )}
                  {brdPrdText.trim() && (
                    <span className="badge text-xs bg-blue-100 text-blue-700">BRD/PRD</span>
                  )}
                  {selectedRefTcIds.size > 0 && (
                    <span className="badge text-xs bg-purple-100 text-purple-700">{selectedRefTcIds.size} reference TCs</span>
                  )}
                  {kbCount > 0 && (
                    <span className="badge text-xs bg-green-100 text-green-700">{kbCount} KB entries</span>
                  )}
                </span>
              </div>
            </div>
          )}

          <div className="space-y-5">
            {/* ═══ Requirements / Use Cases Panel ═══ */}
            {requirements.length > 0 && (
              <div className="border border-teal-200 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowReqPanel(!showReqPanel)}
                  className="w-full flex items-center justify-between p-3 bg-teal-50 hover:bg-teal-100 transition-colors"
                >
                  <div className="flex items-center gap-2 text-sm font-medium text-teal-800">
                    <ClipboardDocumentListIcon className="w-4 h-4 text-teal-600" />
                    Requirements / Use Cases
                    <span className="badge text-xs bg-teal-200 text-teal-800">
                      {selectedReqIds.size}/{requirements.length} selected
                    </span>
                  </div>
                  {showReqPanel ? (
                    <ChevronUpIcon className="w-4 h-4 text-teal-600" />
                  ) : (
                    <ChevronDownIcon className="w-4 h-4 text-teal-600" />
                  )}
                </button>
                {showReqPanel && (
                  <div className="p-3 space-y-2 max-h-60 overflow-y-auto bg-white">
                    <div className="flex justify-between mb-2">
                      <button
                        type="button"
                        onClick={() => setSelectedReqIds(new Set(requirements.map((r) => r.id)))}
                        className="text-xs text-teal-600 hover:text-teal-800 font-medium"
                      >
                        Select All
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedReqIds(new Set())}
                        className="text-xs text-gray-500 hover:text-gray-700 font-medium"
                      >
                        Clear
                      </button>
                    </div>
                    {requirements.map((req) => (
                      <label
                        key={req.id}
                        className="flex items-start gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedReqIds.has(req.id)}
                          onChange={() => toggleReq(req.id)}
                          className="mt-0.5 rounded border-gray-300 text-fg-teal focus:ring-fg-teal"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold text-teal-700">{req.req_id}</span>
                            <span className={`badge text-[10px] ${
                              req.priority === 'high' ? 'bg-red-100 text-red-700' :
                              req.priority === 'medium' ? 'bg-orange-100 text-orange-700' :
                              'bg-gray-100 text-gray-600'
                            }`}>
                              {req.priority}
                            </span>
                            {req.source && (
                              <span className="badge text-[10px] bg-blue-50 text-blue-600">{req.source}</span>
                            )}
                          </div>
                          <p className="text-sm text-fg-dark mt-0.5">{req.title}</p>
                          {req.description && (
                            <p className="text-xs text-fg-mid mt-0.5 line-clamp-2">{req.description}</p>
                          )}
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ═══ BRD/PRD Document Context ═══ */}
            <div className="border border-blue-200 rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setShowBrdPanel(!showBrdPanel)}
                className="w-full flex items-center justify-between p-3 bg-blue-50 hover:bg-blue-100 transition-colors"
              >
                <div className="flex items-center gap-2 text-sm font-medium text-blue-800">
                  <DocumentTextIcon className="w-4 h-4 text-blue-600" />
                  BRD / PRD Document Text
                  {brdPrdText.trim() && (
                    <span className="badge text-xs bg-blue-200 text-blue-800">
                      {brdPrdText.trim().split(/\s+/).length} words
                    </span>
                  )}
                </div>
                {showBrdPanel ? (
                  <ChevronUpIcon className="w-4 h-4 text-blue-600" />
                ) : (
                  <ChevronDownIcon className="w-4 h-4 text-blue-600" />
                )}
              </button>
              {showBrdPanel && (
                <div className="p-3 bg-white">
                  <p className="text-xs text-fg-mid mb-2">
                    Paste BRD/PRD content here for richer, more accurate test generation. The AI will use business rules, acceptance criteria, and feature descriptions to create targeted test cases.
                  </p>
                  <textarea
                    value={brdPrdText}
                    onChange={(e) => setBrdPrdText(e.target.value)}
                    placeholder="Paste your BRD/PRD document content here...&#10;&#10;e.g., Feature: User Authentication&#10;- Users must be able to login with email and password&#10;- Failed login attempts should be rate-limited after 5 tries&#10;- Password reset via email link with 24h expiry..."
                    rows={8}
                    className="input-field text-sm"
                  />
                  <p className="text-xs text-fg-mid mt-1">
                    {brdPrdText.length > 0 ? `${brdPrdText.length.toLocaleString()} characters` : 'No content yet'} • Max ~8,000 characters will be sent
                  </p>
                </div>
              )}
            </div>

            {/* ═══ Reference Test Cases ═══ */}
            {existingTestCases.length > 0 && (
              <div className="border border-purple-200 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowRefPanel(!showRefPanel)}
                  className="w-full flex items-center justify-between p-3 bg-purple-50 hover:bg-purple-100 transition-colors"
                >
                  <div className="flex items-center gap-2 text-sm font-medium text-purple-800">
                    <ClipboardDocumentListIcon className="w-4 h-4 text-purple-600" />
                    Reference Test Cases (style guide)
                    {selectedRefTcIds.size > 0 && (
                      <span className="badge text-xs bg-purple-200 text-purple-800">
                        {selectedRefTcIds.size} selected
                      </span>
                    )}
                  </div>
                  {showRefPanel ? (
                    <ChevronUpIcon className="w-4 h-4 text-purple-600" />
                  ) : (
                    <ChevronDownIcon className="w-4 h-4 text-purple-600" />
                  )}
                </button>
                {showRefPanel && (
                  <div className="p-3 space-y-2 max-h-60 overflow-y-auto bg-white">
                    <p className="text-xs text-fg-mid mb-2">
                      Select existing test cases as examples — the AI will match their style, detail level, and format.
                    </p>
                    {existingTestCases.slice(0, 20).map((tc) => (
                      <label
                        key={tc.id}
                        className="flex items-start gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedRefTcIds.has(tc.id)}
                          onChange={() => toggleRefTc(tc.id)}
                          className="mt-0.5 rounded border-gray-300 text-purple-500 focus:ring-purple-500"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold text-purple-700">{tc.test_case_id}</span>
                            <span className={`badge text-[10px] ${
                              tc.execution_type === 'api' ? 'bg-indigo-100 text-indigo-700' :
                              tc.execution_type === 'ui' ? 'bg-purple-100 text-purple-700' :
                              tc.execution_type === 'sql' ? 'bg-amber-100 text-amber-700' :
                              'bg-gray-100 text-gray-600'
                            }`}>
                              {tc.execution_type}
                            </span>
                            <span className={`badge text-[10px] ${
                              tc.priority === 'P1' ? 'bg-red-100 text-red-700' :
                              tc.priority === 'P2' ? 'bg-orange-100 text-orange-700' :
                              'bg-gray-100 text-gray-600'
                            }`}>
                              {tc.priority}
                            </span>
                          </div>
                          <p className="text-sm text-fg-dark mt-0.5 truncate">{tc.title}</p>
                        </div>
                      </label>
                    ))}
                    {existingTestCases.length > 20 && (
                      <p className="text-xs text-fg-mid text-center py-1">
                        Showing first 20 of {existingTestCases.length} test cases
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Count slider */}
            <div>
              <label className="label">Number of Test Cases: <strong>{count}</strong></label>
              <input
                type="range"
                min="5"
                max="50"
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full accent-fg-teal"
              />
              <div className="flex justify-between text-xs text-fg-mid">
                <span>5</span>
                <span>50</span>
              </div>
            </div>

            {/* Template selection */}
            {templates.length > 0 && (
              <div>
                <label className="label">Template (optional)</label>
                <select
                  value={selectedTemplate || ''}
                  onChange={(e) => setSelectedTemplate(e.target.value || null)}
                  className="input-field"
                >
                  <option value="">No template</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>{t.name} ({t.domain})</option>
                  ))}
                </select>
              </div>
            )}

            {/* Execution Type */}
            <div>
              <label className="label">Execution Type</label>
              <p className="text-xs text-fg-mid mb-2">How should these test cases be executed?</p>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { key: '', label: 'Auto-detect', icon: '🤖', desc: 'AI infers from test steps' },
                  { key: 'api', label: 'API', icon: '🌐', desc: 'REST/HTTP testing' },
                  { key: 'sql', label: 'SQL', icon: '🗄️', desc: 'Database / ETL' },
                  { key: 'ui', label: 'UI', icon: '🖥️', desc: 'Playwright browser' },
                ].map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setExecutionType(t.key)}
                    className={`p-2 rounded-lg border-2 text-center transition-all ${
                      executionType === t.key
                        ? 'border-teal-500 bg-teal-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <span className="text-lg block">{t.icon}</span>
                    <span className="text-xs font-semibold text-fg-dark block">{t.label}</span>
                    <span className="text-[10px] text-fg-mid block">{t.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Priority + Category */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Default Priority (optional)</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="input-field"
                >
                  <option value="">Auto-assign</option>
                  <option value="P1">P1 - Critical</option>
                  <option value="P2">P2 - High</option>
                  <option value="P3">P3 - Medium</option>
                  <option value="P4">P4 - Low</option>
                </select>
              </div>
              <div>
                <label className="label">Default Category (optional)</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="input-field"
                >
                  <option value="">Auto-assign</option>
                  <option value="functional">Functional</option>
                  <option value="integration">Integration</option>
                  <option value="regression">Regression</option>
                  <option value="smoke">Smoke</option>
                  <option value="e2e">End-to-End</option>
                </select>
              </div>
            </div>

            {/* Additional context */}
            <div>
              <label className="label">Additional Context (optional)</label>
              <textarea
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
                placeholder="Any extra details, specific scenarios, edge cases to cover..."
                rows={3}
                className="input-field"
              />
            </div>

            {/* Knowledge Base context indicator */}
            {kbCount > 0 && (
              <div className="p-3 rounded-lg bg-teal-50 border border-teal-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-teal-800">
                    <BookOpenIcon className="w-4 h-4 text-teal-600" />
                    <span>
                      <strong>{kbCount}</strong> knowledge base {kbCount === 1 ? 'entry' : 'entries'} will enhance generation
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowKbPreview(!showKbPreview)}
                    className="text-xs text-teal-600 hover:text-teal-800 underline"
                  >
                    {showKbPreview ? 'Hide' : 'Preview'}
                  </button>
                </div>
                {showKbPreview && (
                  <div className="mt-3 space-y-2 max-h-48 overflow-y-auto">
                    {kbEntries.map((entry) => (
                      <div key={entry.id} className="text-xs bg-white/60 rounded p-2">
                        <span className="font-semibold text-teal-900">{entry.title}</span>
                        <span className="ml-2 text-[10px] text-teal-600 uppercase">{entry.entry_type?.replace(/_/g, ' ')}</span>
                        <p className="text-teal-700 mt-0.5 line-clamp-2">{entry.content?.substring(0, 150)}...</p>
                      </div>
                    ))}
                  </div>
                )}
                <a
                  href="/knowledge"
                  className="text-xs text-teal-600 hover:text-teal-800 mt-2 inline-block"
                  onClick={(e) => { e.preventDefault(); window.open('/knowledge', '_blank'); }}
                >
                  Add more reference patterns &rarr;
                </a>
              </div>
            )}
          </div>

          <div className="flex justify-between mt-6">
            <button onClick={() => setStep(0)} className="btn-ghost">
              Back
            </button>
            <button onClick={handleGenerate} className="btn-primary flex items-center gap-2">
              <SparklesIcon className="w-4 h-4" />
              Generate {count} Test Cases
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Generating (loading) */}
      {step === 2 && generating && (
        <div className="card-static p-12 text-center animate-fade-in">
          <div className="w-16 h-16 rounded-full bg-fg-tealLight mx-auto mb-5 flex items-center justify-center">
            <SparklesIcon className="w-8 h-8 text-fg-teal animate-pulse" />
          </div>
          <h2 className="text-lg font-bold text-fg-navy mb-2">Generating Test Cases</h2>
          <p className="text-sm text-fg-mid mb-4">
            Using Claude Sonnet with {contextSourceCount > 0 ? `${contextSourceCount} context sources` : 'your description'}...
          </p>
          <div className="flex justify-center gap-3 mb-6 flex-wrap">
            {requirements.length > 0 && selectedReqIds.size > 0 && (
              <span className="badge text-xs bg-teal-100 text-teal-700">📋 {selectedReqIds.size} requirements</span>
            )}
            {brdPrdText.trim() && (
              <span className="badge text-xs bg-blue-100 text-blue-700">📄 BRD/PRD context</span>
            )}
            {selectedRefTcIds.size > 0 && (
              <span className="badge text-xs bg-purple-100 text-purple-700">📎 {selectedRefTcIds.size} reference TCs</span>
            )}
            {kbCount > 0 && (
              <span className="badge text-xs bg-green-100 text-green-700">📚 {kbCount} KB patterns</span>
            )}
          </div>
          <div className="w-64 mx-auto">
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-fg-teal to-fg-green rounded-full animate-pulse" style={{ width: '75%' }} />
            </div>
          </div>
          <p className="text-xs text-fg-mid mt-3">This may take 30-90 seconds with full context</p>
        </div>
      )}

      {/* Step 4: Review results */}
      {step === 3 && (
        <div className="animate-fade-in">
          {/* Generation metadata */}
          {resultMeta && (
            <div className="flex flex-wrap items-center gap-4 mb-5 text-sm text-fg-mid">
              <span className="flex items-center gap-1">
                <CheckCircleIcon className="w-4 h-4 text-green-500" />
                {resultMeta.count} test cases generated
              </span>
              <span className="flex items-center gap-1">
                <ClockIcon className="w-4 h-4" />
                {resultMeta.duration}s
              </span>
              {results[0]?.generated_by_model && (
                <span className="flex items-center gap-1">
                  <CpuChipIcon className="w-4 h-4" />
                  {results[0].generated_by_model}
                </span>
              )}
              {kbCount > 0 && (
                <span className="flex items-center gap-1 text-teal-600">
                  <BookOpenIcon className="w-4 h-4" />
                  Enhanced with {kbCount} KB {kbCount === 1 ? 'pattern' : 'patterns'}
                </span>
              )}
            </div>
          )}

          {/* Summary bar */}
          <div className="card-static p-4 mb-5 flex items-center justify-between">
            <div className="flex items-center gap-4 text-sm">
              <span className="text-green-600 font-medium">{approvedCount} approved</span>
              <span className="text-red-500 font-medium">{rejectedCount} rejected</span>
            </div>
            <button
              onClick={handleFinalize}
              disabled={finalizing}
              className="btn-primary text-sm flex items-center gap-2"
            >
              {finalizing ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                  Removing rejected...
                </>
              ) : rejectedCount > 0 ? (
                `Confirm — Keep ${approvedCount}, Remove ${rejectedCount}`
              ) : (
                'Done — View Project'
              )}
            </button>
          </div>

          {/* Results list */}
          <div className="space-y-3">
            {results.map((tc) => {
              const decision = decisions[tc.id] || 'approve';
              return (
                <div
                  key={tc.id}
                  className={`card-static p-4 border-l-4 transition-all
                    ${decision === 'approve' ? 'border-l-green-400' :
                      decision === 'reject' ? 'border-l-red-400 opacity-60' :
                      'border-l-gray-300'}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono font-bold text-fg-tealDark">{tc.test_case_id}</span>
                        <span className={`badge text-xs ${
                          tc.priority === 'P1' ? 'bg-red-100 text-red-700' :
                          tc.priority === 'P2' ? 'bg-orange-100 text-orange-700' :
                          tc.priority === 'P3' ? 'bg-blue-100 text-blue-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {tc.priority}
                        </span>
                        <span className="badge badge-gray text-xs capitalize">{tc.category}</span>
                        {tc.execution_type && (
                          <span className={`badge text-xs ${
                            tc.execution_type === 'api' ? 'bg-indigo-100 text-indigo-700' :
                            tc.execution_type === 'ui' ? 'bg-purple-100 text-purple-700' :
                            tc.execution_type === 'sql' ? 'bg-amber-100 text-amber-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {tc.execution_type}
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-medium text-fg-dark">{tc.title}</p>
                      {tc.description && (
                        <p className="text-xs text-fg-mid mt-1 line-clamp-2">{tc.description}</p>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1 ml-3 flex-shrink-0">
                      <button
                        onClick={() => setDecisions({ ...decisions, [tc.id]: 'approve' })}
                        className={`p-1.5 rounded-lg transition-colors ${
                          decision === 'approve' ? 'bg-green-100 text-green-600' : 'text-gray-300 hover:text-green-500'
                        }`}
                        title="Approve"
                      >
                        <CheckCircleIcon className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => navigate(`/projects/${id}/test-cases/${tc.id}`)}
                        className="p-1.5 rounded-lg text-gray-300 hover:text-fg-teal transition-colors"
                        title="Edit"
                      >
                        <PencilSquareIcon className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => setDecisions({ ...decisions, [tc.id]: 'reject' })}
                        className={`p-1.5 rounded-lg transition-colors ${
                          decision === 'reject' ? 'bg-red-100 text-red-500' : 'text-gray-300 hover:text-red-400'
                        }`}
                        title="Reject"
                      >
                        <XCircleIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>

                  {/* Test steps preview */}
                  {tc.test_steps && tc.test_steps.length > 0 && (
                    <div className="mt-2 text-xs text-fg-mid">
                      <span className="font-medium">{tc.test_steps.length} steps:</span>{' '}
                      {tc.test_steps.slice(0, 2).map((s) => s.action).join(' / ')}
                      {tc.test_steps.length > 2 && '...'}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

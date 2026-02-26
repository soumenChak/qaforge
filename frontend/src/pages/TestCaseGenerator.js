import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectsAPI, testCasesAPI, templatesAPI } from '../services/api';
import {
  SparklesIcon,
  CheckCircleIcon,
  XCircleIcon,
  PencilSquareIcon,
  ArrowLeftIcon,
  ClockIcon,
  CpuChipIcon,
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

  const handleGenerate = async () => {
    setStep(2);
    setGenerating(true);
    setGenerationError('');

    const startTime = Date.now();

    try {
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

  const approvedCount = Object.values(decisions).filter((d) => d === 'approve').length;
  const rejectedCount = Object.values(decisions).filter((d) => d === 'reject').length;

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
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g., We have a Reltio MDM system that merges customer records using match rules. The golden record should merge name, address, and phone fields from multiple source systems (SAP, Salesforce, Oracle). Test the merge logic, survivorship rules, and data quality checks..."
            rows={8}
            className="input-field mb-4"
            autoFocus
          />
          <div className="flex justify-end">
            <button
              onClick={() => setStep(1)}
              disabled={!description.trim()}
              className="btn-primary"
            >
              Next: Configure
            </button>
          </div>
        </div>
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

          <div className="space-y-5">
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
          <p className="text-sm text-fg-mid mb-6">
            Our AI agents are analyzing your description and creating comprehensive test cases...
          </p>
          <div className="w-64 mx-auto">
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-fg-teal to-fg-green rounded-full animate-pulse" style={{ width: '75%' }} />
            </div>
          </div>
          <p className="text-xs text-fg-mid mt-3">This may take 15-60 seconds depending on complexity</p>
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
            </div>
          )}

          {/* Summary bar */}
          <div className="card-static p-4 mb-5 flex items-center justify-between">
            <div className="flex items-center gap-4 text-sm">
              <span className="text-green-600 font-medium">{approvedCount} approved</span>
              <span className="text-red-500 font-medium">{rejectedCount} rejected</span>
            </div>
            <button
              onClick={() => navigate(`/projects/${id}`)}
              className="btn-primary text-sm"
            >
              Done -- View Project
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

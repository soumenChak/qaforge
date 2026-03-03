import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { testCasesAPI, testPlansAPI, executionsAPI, projectsAPI } from '../services/api';
import Breadcrumb from '../components/Breadcrumb';
import ProofViewer from '../components/ProofViewer';
import { CheckCircleIcon, XCircleIcon, ClockIcon, ChevronDownIcon, ChevronUpIcon, EyeIcon, DocumentArrowDownIcon, TrashIcon } from '@heroicons/react/24/outline';

const STATUS_CHIP = { draft: 'badge-gray', reviewed: 'bg-blue-100 text-blue-800', approved: 'badge-green', executed: 'bg-orange-100 text-orange-800', passed: 'badge-green', failed: 'badge-red' };
const CP_STATUS = { pending: 'badge-yellow', approved: 'badge-green', rejected: 'badge-red', needs_rework: 'bg-orange-100 text-orange-800' };
const REV_STATUS = { pending: 'badge-yellow', approved: 'badge-green', rejected: 'badge-red' };

const Chip = ({ status }) => <span className={`badge ${STATUS_CHIP[status] || 'badge-gray'}`}>{status}</span>;
const Spinner = () => <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-fg-teal" /></div>;
function StatCard({ label, value, color, icon }) {
  return (
    <div className="text-center p-3 rounded-lg bg-gray-50">
      {icon && <div className="flex justify-center mb-1">{icon}</div>}
      <p className={`text-2xl font-bold ${color || 'text-fg-navy'}`}>{value}</p>
      <p className="text-xs text-fg-mid mt-0.5 capitalize">{label}</p>
    </div>
  );
}

export default function TestPlanDetail() {
  const { id: projectId, planId } = useParams();
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('test_cases');

  // Test Cases
  const [testCases, setTestCases] = useState([]);
  const [tcLoading, setTcLoading] = useState(false);
  const [selectedTcIds, setSelectedTcIds] = useState(new Set());
  const [bulkApproving, setBulkApproving] = useState(false);
  // Executions
  const [executions, setExecutions] = useState([]);
  const [execLoading, setExecLoading] = useState(false);
  const [expandedExecId, setExpandedExecId] = useState(null);
  const [reviewingExecId, setReviewingExecId] = useState(null);
  const [reviewComment, setReviewComment] = useState('');
  // Proof Viewer
  const [selectedProof, setSelectedProof] = useState(null);
  // Traceability & Summary
  const [traceability, setTraceability] = useState(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [sumLoading, setSumLoading] = useState(false);
  // Playbook
  const [projectData, setProjectData] = useState(null);
  const [playbookTcData, setPlaybookTcData] = useState([]);

  // ── Loaders ──
  const load = useCallback(async (fn, setter, loadingSetter) => {
    loadingSetter(true);
    try { const r = await fn(); setter(r.data); } catch (e) { console.error(e); } finally { loadingSetter(false); }
  }, []);

  const loadPlan = useCallback(async () => {
    try { setPlan((await testPlansAPI.getById(projectId, planId)).data); }
    catch (e) { console.error('Failed to load plan:', e); }
    finally { setLoading(false); }
  }, [projectId, planId]);

  const loadTC = useCallback(() => load(() => testCasesAPI.list(projectId, { test_plan_id: planId }), setTestCases, setTcLoading), [projectId, planId, load]);
  const loadExec = useCallback(() => load(() => executionsAPI.list(projectId, { test_plan_id: planId }), setExecutions, setExecLoading), [projectId, planId, load]);
  const loadTrace = useCallback(() => load(() => testPlansAPI.getTraceability(projectId, planId), setTraceability, setTraceLoading), [projectId, planId, load]);
  const loadSum = useCallback(() => load(() => testPlansAPI.getSummary(projectId, planId), setSummary, setSumLoading), [projectId, planId, load]);

  useEffect(() => { loadPlan(); }, [loadPlan]);
  useEffect(() => { if (activeTab === 'test_cases') loadTC(); }, [activeTab, loadTC]);
  useEffect(() => { if (activeTab === 'executions') loadExec(); }, [activeTab, loadExec]);
  useEffect(() => { if (activeTab === 'traceability') loadTrace(); }, [activeTab, loadTrace]);
  useEffect(() => { if (activeTab === 'summary') loadSum(); }, [activeTab, loadSum]);
  useEffect(() => {
    if (activeTab === 'playbook') {
      projectsAPI.getById(projectId).then(r => setProjectData(r.data)).catch(() => {});
      testCasesAPI.list(projectId, { test_plan_id: planId }).then(r => setPlaybookTcData(r.data || [])).catch(() => {});
    }
  }, [activeTab, projectId, planId]);

  // ── Handlers ──
  const toggleTc = (id) => setSelectedTcIds(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const selectAllTc = () => setSelectedTcIds(p => p.size === testCases.length ? new Set() : new Set(testCases.map(t => t.id)));

  const bulkApprove = async () => {
    if (!selectedTcIds.size) return;
    setBulkApproving(true);
    try { await testCasesAPI.bulkStatus(projectId, [...selectedTcIds], 'approved'); setSelectedTcIds(new Set()); loadTC(); }
    catch (e) { alert(e.response?.data?.detail || 'Bulk approve failed.'); }
    finally { setBulkApproving(false); }
  };

  const execReview = async (id, status) => {
    try { await executionsAPI.review(projectId, id, { status, comment: reviewComment }); setReviewingExecId(null); setReviewComment(''); loadExec(); }
    catch (e) { alert(e.response?.data?.detail || 'Review failed.'); }
  };

  // ── Guards ──
  if (loading) return <div className="page-container"><Spinner /></div>;
  if (!plan) return <div className="page-container"><p className="text-fg-mid">Test plan not found.</p><button onClick={() => navigate(-1)} className="btn-secondary mt-4">Go Back</button></div>;

  const tabs = [
    { key: 'test_cases', label: 'Test Cases' },
    { key: 'executions', label: 'Executions' },
    { key: 'traceability', label: 'Traceability' },
    { key: 'summary', label: 'Summary' },
    { key: 'playbook', label: 'Playbook' },
  ];

  const covPct = traceability?.coverage_percentage ?? 0;
  const covTextCls = covPct >= 80 ? 'text-green-600' : covPct >= 50 ? 'text-yellow-600' : 'text-red-600';
  const covBarCls = covPct >= 80 ? 'bg-green-500' : covPct >= 50 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <Breadcrumb items={[{ label: 'Projects', to: '/projects' }, { label: plan.project_name || 'Project', to: `/projects/${projectId}` }, { label: plan.name || 'Test Plan' }]} />
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-fg-navy mt-2">{plan.name}</h1>
          <button
            onClick={async () => {
              if (!window.confirm(`Delete test plan "${plan.name}"? This cannot be undone.`)) return;
              try {
                await testPlansAPI.delete(projectId, planId);
                navigate(`/projects/${projectId}`, { state: { tab: 'test_plans' } });
              } catch (err) {
                alert('Failed to delete test plan.');
              }
            }}
            className="btn-secondary text-sm flex items-center gap-1.5 border-red-200 text-red-600 hover:bg-red-50"
          >
            <TrashIcon className="w-4 h-4" />
            Delete Plan
          </button>
        </div>
        {plan.description && <p className="text-sm text-fg-mid mt-1">{plan.description}</p>}
        <div className="flex items-center gap-2 mt-2">
          <span className={`badge ${plan.status === 'active' ? 'badge-green' : plan.status === 'completed' ? 'badge-teal' : 'badge-gray'}`}>{plan.status}</span>
          {plan.version && <span className="badge badge-gray">v{plan.version}</span>}
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 mb-6 overflow-x-auto">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors -mb-px whitespace-nowrap ${activeTab === t.key ? 'border-fg-teal text-fg-tealDark' : 'border-transparent text-fg-mid hover:text-fg-dark hover:border-gray-300'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Test Cases ── */}
      {activeTab === 'test_cases' && <div className="animate-fade-in">
        {selectedTcIds.size > 0 && <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-fg-mid">{selectedTcIds.size} selected</span>
          <button onClick={bulkApprove} disabled={bulkApproving} className="btn-primary text-sm flex items-center gap-1">
            <CheckCircleIcon className="w-4 h-4" />{bulkApproving ? 'Approving...' : 'Bulk Approve'}
          </button>
        </div>}
        {tcLoading ? <Spinner /> : !testCases.length ? <p className="text-fg-mid text-sm py-8 text-center">No test cases linked to this plan.</p> : (
          <div className="table-container"><table className="min-w-full divide-y divide-gray-200">
            <thead><tr className="table-header">
              <th className="px-4 py-3"><input type="checkbox" checked={selectedTcIds.size === testCases.length && testCases.length > 0} onChange={selectAllTc} className="rounded border-gray-300" /></th>
              <th className="px-4 py-3">TC ID</th><th className="px-4 py-3">Title</th><th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Priority</th><th className="px-4 py-3">Execution Type</th><th className="px-4 py-3">Status</th>
            </tr></thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {testCases.map(tc => <tr key={tc.id} className="table-row">
                <td className="px-4 py-3"><input type="checkbox" checked={selectedTcIds.has(tc.id)} onChange={() => toggleTc(tc.id)} className="rounded border-gray-300" /></td>
                <td className="px-4 py-3 text-sm font-mono text-fg-dark">{tc.test_case_id}</td>
                <td className="px-4 py-3 text-sm text-fg-dark max-w-xs truncate">{tc.title}</td>
                <td className="px-4 py-3 text-sm text-fg-mid">{tc.category}</td>
                <td className="px-4 py-3"><Chip status={tc.priority} /></td>
                <td className="px-4 py-3 text-sm text-fg-mid">{tc.execution_type}</td>
                <td className="px-4 py-3"><Chip status={tc.status} /></td>
              </tr>)}
            </tbody>
          </table></div>
        )}
      </div>}

      {/* ── Executions ── */}
      {activeTab === 'executions' && <div className="animate-fade-in">
        {execLoading ? <Spinner /> : !executions.length ? <p className="text-fg-mid text-sm py-8 text-center">No executions recorded yet.</p> : (
          <div className="table-container"><table className="min-w-full divide-y divide-gray-200">
            <thead><tr className="table-header">
              <th className="px-4 py-3 w-8" /><th className="px-4 py-3">Test Case</th><th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Executed By</th><th className="px-4 py-3">Duration</th><th className="px-4 py-3">Review</th>
              <th className="px-4 py-3">Executed At</th><th className="px-4 py-3">Actions</th>
            </tr></thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {executions.map(ex => <React.Fragment key={ex.id}>
                <tr className="table-row">
                  <td className="px-4 py-3">
                    <button onClick={() => setExpandedExecId(expandedExecId === ex.id ? null : ex.id)} className="text-fg-mid hover:text-fg-dark">
                      {expandedExecId === ex.id ? <ChevronUpIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-fg-dark">{ex.test_case_id}</td>
                  <td className="px-4 py-3"><Chip status={ex.status} /></td>
                  <td className="px-4 py-3 text-sm text-fg-mid">{ex.executed_by || '-'}</td>
                  <td className="px-4 py-3 text-sm text-fg-mid">{ex.duration_ms != null ? `${ex.duration_ms}ms` : ex.duration != null ? `${ex.duration}s` : '-'}</td>
                  <td className="px-4 py-3"><span className={`badge ${REV_STATUS[ex.review_status] || 'badge-gray'}`}>{ex.review_status || 'pending'}</span></td>
                  <td className="px-4 py-3 text-sm text-fg-mid">{ex.executed_at ? new Date(ex.executed_at).toLocaleString() : '-'}</td>
                  <td className="px-4 py-3">
                    {reviewingExecId === ex.id ? (
                      <div className="flex flex-col gap-2 min-w-[200px]">
                        <input type="text" placeholder="Comment (optional)" value={reviewComment} onChange={e => setReviewComment(e.target.value)} className="input-field text-xs" />
                        <div className="flex gap-1">
                          <button onClick={() => execReview(ex.id, 'approved')} className="btn-primary text-xs px-2 py-1 flex items-center gap-1"><CheckCircleIcon className="w-3.5 h-3.5" /> Approve</button>
                          <button onClick={() => execReview(ex.id, 'rejected')} className="btn-danger text-xs px-2 py-1 flex items-center gap-1"><XCircleIcon className="w-3.5 h-3.5" /> Reject</button>
                          <button onClick={() => { setReviewingExecId(null); setReviewComment(''); }} className="btn-ghost text-xs px-2 py-1">Cancel</button>
                        </div>
                      </div>
                    ) : <button onClick={() => setReviewingExecId(ex.id)} className="btn-secondary text-xs px-2 py-1">Review</button>}
                  </td>
                </tr>
                {expandedExecId === ex.id && <tr><td colSpan={8} className="px-8 py-4 bg-gray-50">
                  {ex.actual_result && <div className="mb-3">
                    <p className="text-xs font-semibold text-fg-mid mb-1 uppercase tracking-wider">Actual Result</p>
                    <p className="text-sm text-fg-dark">{ex.actual_result}</p>
                  </div>}
                  {ex.error_message && <div className="mb-3">
                    <p className="text-xs font-semibold text-red-500 mb-1 uppercase tracking-wider">Error</p>
                    <pre className="text-xs text-red-700 bg-red-50 p-2 rounded overflow-x-auto">{ex.error_message}</pre>
                  </div>}
                  {ex.proof_artifacts?.length > 0 ? (<div>
                    <p className="text-xs font-semibold text-fg-mid mb-2 uppercase tracking-wider">Proof Artifacts ({ex.proof_artifacts.length})</p>
                    <div className="flex flex-wrap gap-2">
                      {ex.proof_artifacts.map((a, i) => (
                        <button key={i} onClick={() => setSelectedProof(a)}
                          className="card-static px-3 py-2 text-xs cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-colors flex items-center gap-2 border border-gray-200 rounded">
                          <EyeIcon className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                          <span className="font-medium text-fg-dark">{a.title || 'Untitled'}</span>
                          <span className="badge badge-gray ml-1">{a.proof_type || a.type}</span>
                        </button>
                      ))}
                    </div>
                  </div>) : <p className="text-xs text-fg-mid">No proof artifacts for this execution.</p>}
                </td></tr>}
              </React.Fragment>)}
            </tbody>
          </table></div>
        )}
      </div>}

      {/* ── Traceability ── */}
      {activeTab === 'traceability' && <div className="animate-fade-in">
        {traceLoading ? <Spinner /> : !traceability ? <p className="text-fg-mid text-sm py-8 text-center">No traceability data available.</p> : (<>
          <div className="card p-5 mb-6"><div className="flex items-center gap-4">
            <div>
              <p className="text-xs font-semibold text-fg-mid uppercase tracking-wider">Requirement Coverage</p>
              <p className={`text-3xl font-bold mt-1 ${covTextCls}`}>
                {traceability.coverage_percentage != null ? `${traceability.coverage_percentage.toFixed(1)}%` : 'N/A'}
              </p>
            </div>
            <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-500 ${covBarCls}`} style={{ width: `${Math.min(covPct, 100)}%` }} />
            </div>
          </div></div>
          {traceability.matrix?.length > 0 ? (
            <div className="table-container"><table className="min-w-full divide-y divide-gray-200">
              <thead><tr className="table-header">
                <th className="px-4 py-3">Requirement</th><th className="px-4 py-3">Test Cases</th><th className="px-4 py-3">Execution Status</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {traceability.matrix.map((row, i) => {
                  const uncov = !row.test_cases?.length;
                  return <tr key={i} className={uncov ? 'bg-red-50' : 'table-row'}>
                    <td className="px-4 py-3">
                      <span className={`text-sm font-medium ${uncov ? 'text-red-700' : 'text-fg-dark'}`}>{row.requirement_id}</span>
                      {row.requirement_title && <p className="text-xs text-fg-mid mt-0.5">{row.requirement_title}</p>}
                      {uncov && <span className="badge badge-red text-xs mt-1">Uncovered</span>}
                    </td>
                    <td className="px-4 py-3 text-sm text-fg-mid">
                      {row.test_cases?.length ? row.test_cases.map(tc => tc.test_case_id || tc).join(', ') : <span className="text-red-500 italic">None</span>}
                    </td>
                    <td className="px-4 py-3">{row.execution_status ? <Chip status={row.execution_status} /> : <span className="text-xs text-fg-mid">-</span>}</td>
                  </tr>;
                })}
              </tbody>
            </table></div>
          ) : <p className="text-fg-mid text-sm text-center py-4">No matrix data available.</p>}
        </>)}
      </div>}

      {/* ── Summary ── */}
      {activeTab === 'summary' && <div className="animate-fade-in">
        {sumLoading ? <Spinner /> : !summary ? <p className="text-fg-mid text-sm py-8 text-center">No summary data available.</p> : (() => {
          const tc = summary.test_cases || {};
          const ex = summary.executions || {};
          const rv = summary.reviews || {};
          return (
          <div className="space-y-6">
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-fg-navy mb-4 uppercase tracking-wider">Test Cases</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="Total" value={tc.total ?? 0} />
                {tc.by_status && Object.entries(tc.by_status).map(([k, v]) => <StatCard key={k} label={k} value={v} />)}
              </div>
              {(tc.by_category || tc.by_priority) && <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mt-4">
                {tc.by_category && <div>
                  <p className="text-xs font-semibold text-fg-mid mb-2">By Category</p>
                  {Object.entries(tc.by_category).map(([k, v]) => <div key={k} className="flex justify-between text-sm"><span className="text-fg-mid capitalize">{k}</span><span className="font-medium text-fg-dark">{v}</span></div>)}
                </div>}
                {tc.by_priority && <div>
                  <p className="text-xs font-semibold text-fg-mid mb-2">By Priority</p>
                  {Object.entries(tc.by_priority).map(([k, v]) => <div key={k} className="flex justify-between text-sm"><span className="text-fg-mid">{k}</span><span className="font-medium text-fg-dark">{v}</span></div>)}
                </div>}
              </div>}
            </div>

            <div className="card p-5">
              <h3 className="text-sm font-semibold text-fg-navy mb-4 uppercase tracking-wider">Execution Results</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="Total Executed" value={ex.total ?? 0} />
                <StatCard label="Passed" value={ex.passed ?? 0} color="text-green-600" />
                <StatCard label="Failed" value={ex.failed ?? 0} color="text-red-600" />
                <StatCard label="Pass Rate" value={ex.pass_rate != null ? `${ex.pass_rate.toFixed(1)}%` : 'N/A'}
                  color={(ex.pass_rate ?? 0) >= 80 ? 'text-green-600' : (ex.pass_rate ?? 0) >= 50 ? 'text-yellow-600' : 'text-red-600'} />
              </div>
            </div>

            <div className="card p-5">
              <h3 className="text-sm font-semibold text-fg-navy mb-4 uppercase tracking-wider">Reviews</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <StatCard label="Pending" value={rv.pending ?? 0} icon={<ClockIcon className="w-5 h-5 text-yellow-500" />} />
                <StatCard label="Approved" value={rv.approved ?? 0} icon={<CheckCircleIcon className="w-5 h-5 text-green-500" />} />
                <StatCard label="Rejected" value={rv.rejected ?? 0} icon={<XCircleIcon className="w-5 h-5 text-red-500" />} />
              </div>
            </div>

            {summary.checkpoints?.length > 0 && <div className="card p-5">
              <h3 className="text-sm font-semibold text-fg-navy mb-4 uppercase tracking-wider">Checkpoint Status</h3>
              <div className="space-y-2">
                {summary.checkpoints.map((cp, i) => <div key={i} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                  <span className="text-sm text-fg-dark capitalize">{cp.type?.replace(/_/g, ' ')}</span>
                  <span className={`badge ${CP_STATUS[cp.status] || 'badge-gray'}`}>{cp.status}</span>
                </div>)}
              </div>
            </div>}
          </div>
          );
        })()}
      </div>}

      {/* ── Playbook ── */}
      {activeTab === 'playbook' && <div className="animate-fade-in">
        {(() => {
          const ec = plan.execution_config || {};
          const connections = projectData?.app_profile?.connections || {};
          const usedConns = ec.connection_refs || Object.keys(connections);

          const exportMarkdown = () => {
            let md = `# Execution Playbook: ${plan.name}\n\n`;
            md += `**Plan Type:** ${plan.plan_type}  \n`;
            md += `**Status:** ${plan.status}  \n`;
            if (ec.environment) md += `**Environment:** ${ec.environment}  \n`;
            if (ec.estimated_duration_minutes) md += `**Estimated Duration:** ${ec.estimated_duration_minutes} minutes  \n`;
            md += `\n---\n\n`;

            if (ec.required_env_vars?.length) {
              md += `## Required Environment Variables\n\n`;
              ec.required_env_vars.forEach(v => {
                const name = typeof v === 'string' ? v : v.name;
                const desc = typeof v === 'string' ? '' : v.description || '';
                md += `- \`${name}\`${desc ? ` — ${desc}` : ''}\n`;
              });
              md += `\n`;
            }

            if (ec.prerequisites?.length) {
              md += `## Prerequisites\n\n`;
              ec.prerequisites.forEach((p, i) => md += `${i + 1}. ${p}\n`);
              md += `\n`;
            }

            if (usedConns.length) {
              md += `## Connections\n\n`;
              usedConns.forEach(key => {
                const c = connections[key];
                if (!c) { md += `- **${key}** — (not configured)\n`; return; }
                md += `### ${key} (${c.type})\n`;
                if (c.server_url) md += `- **Server URL:** \`${c.server_url}\`\n`;
                if (c.base_url) md += `- **Base URL:** \`${c.base_url}\`\n`;
                if (c.transport) md += `- **Transport:** ${c.transport}\n`;
                if (c.description) md += `- **Description:** ${c.description}\n`;
                if (c.setup_command) md += `- **Setup:** \`${c.setup_command}\`\n`;
                if (c.env_vars?.length) md += `- **Env Vars:** ${c.env_vars.map(v => `\`${v}\``).join(', ')}\n`;
                md += `\n`;
              });
            }

            md += `## Test Steps\n\n`;
            playbookTcData.forEach((tc, ti) => {
              md += `### ${ti + 1}. ${tc.test_case_id}: ${tc.title}\n\n`;
              md += `**Type:** ${tc.execution_type} | **Priority:** ${tc.priority} | **Category:** ${tc.category}\n\n`;
              (tc.test_steps || []).forEach(step => {
                md += `**Step ${step.step_number}:** ${step.action}\n`;
                md += `- **Expected:** ${step.expected_result}\n`;
                if (step.step_type) md += `- **Step Type:** ${step.step_type}\n`;
                if (step.connection_ref) md += `- **Connection:** \`${step.connection_ref}\`\n`;
                if (step.tool_name) md += `- **Tool:** \`${step.tool_name}\`\n`;
                if (step.tool_params) md += `- **Params:** \`${JSON.stringify(step.tool_params)}\`\n`;
                if (step.method) md += `- **Method:** ${step.method} ${step.endpoint || ''}\n`;
                if (step.sql_script) md += `- **SQL:** \`${step.sql_script}\`\n`;
                if (step.assertions?.length) md += `- **Assertions:** ${JSON.stringify(step.assertions)}\n`;
                md += `\n`;
              });
            });

            if (ec.post_conditions?.length) {
              md += `## Post-Conditions\n\n`;
              ec.post_conditions.forEach((p, i) => md += `${i + 1}. ${p}\n`);
            }

            const blob = new Blob([md], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `playbook-${plan.name.replace(/\s+/g, '-').toLowerCase()}.md`;
            a.click();
            URL.revokeObjectURL(url);
          };

          return (
            <div className="space-y-6 max-w-4xl">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-fg-dark">Execution Playbook</h3>
                  <p className="text-sm text-fg-mid mt-0.5">Auto-generated runbook from structured test steps, connections, and execution config.</p>
                </div>
                <button onClick={exportMarkdown} className="btn btn-secondary text-sm flex items-center gap-2">
                  <DocumentArrowDownIcon className="w-4 h-4" /> Export Markdown
                </button>
              </div>

              {/* Environment & Config */}
              {(ec.environment || ec.estimated_duration_minutes || ec.execution_order) && (
                <div className="card p-5">
                  <h4 className="text-sm font-semibold text-fg-navy mb-3 uppercase tracking-wider">Environment</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
                    {ec.environment && <div><span className="text-fg-mid">Environment:</span><br /><span className="font-medium">{ec.environment}</span></div>}
                    {ec.execution_order && <div><span className="text-fg-mid">Execution Order:</span><br /><span className="font-medium capitalize">{ec.execution_order}</span></div>}
                    {ec.estimated_duration_minutes && <div><span className="text-fg-mid">Est. Duration:</span><br /><span className="font-medium">{ec.estimated_duration_minutes} min</span></div>}
                  </div>
                </div>
              )}

              {/* Required Env Vars */}
              {ec.required_env_vars?.length > 0 && (
                <div className="card p-5">
                  <h4 className="text-sm font-semibold text-fg-navy mb-3 uppercase tracking-wider">Required Environment Variables</h4>
                  <div className="space-y-2">
                    {ec.required_env_vars.map((v, i) => {
                      const name = typeof v === 'string' ? v : v.name;
                      const desc = typeof v === 'string' ? '' : v.description;
                      return (
                        <div key={i} className="flex items-center gap-3 text-sm">
                          <code className="px-2 py-0.5 bg-gray-100 rounded text-xs font-mono font-semibold text-indigo-700">{name}</code>
                          {desc && <span className="text-fg-mid">{desc}</span>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Prerequisites */}
              {ec.prerequisites?.length > 0 && (
                <div className="card p-5">
                  <h4 className="text-sm font-semibold text-fg-navy mb-3 uppercase tracking-wider">Prerequisites</h4>
                  <ol className="list-decimal list-inside space-y-1.5 text-sm text-fg-dark">
                    {ec.prerequisites.map((p, i) => <li key={i}>{p}</li>)}
                  </ol>
                </div>
              )}

              {/* Connections */}
              {usedConns.length > 0 && (
                <div className="card p-5">
                  <h4 className="text-sm font-semibold text-fg-navy mb-3 uppercase tracking-wider">Connections</h4>
                  <div className="space-y-3">
                    {usedConns.map(key => {
                      const c = connections[key];
                      if (!c) return (
                        <div key={key} className="p-3 bg-yellow-50 rounded-lg border border-yellow-200 text-sm">
                          <span className="font-mono font-semibold text-yellow-800">{key}</span>
                          <span className="text-yellow-700 ml-2">Not configured in App Profile</span>
                        </div>
                      );
                      return (
                        <div key={key} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="font-mono font-semibold text-indigo-700 text-sm">{key}</span>
                            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                              c.type === 'mcp' ? 'bg-purple-100 text-purple-700' :
                              c.type === 'rest_api' ? 'bg-blue-100 text-blue-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>{c.type}</span>
                            {c.transport && <span className="text-xs text-fg-mid">({c.transport})</span>}
                          </div>
                          {c.description && <p className="text-xs text-fg-mid">{c.description}</p>}
                          {(c.server_url || c.base_url) && (
                            <code className="text-xs font-mono text-fg-dark mt-1 block">{c.server_url || c.base_url}</code>
                          )}
                          {c.setup_command && (
                            <div className="mt-1.5">
                              <span className="text-[10px] text-fg-mid uppercase font-semibold">Setup:</span>
                              <code className="text-xs font-mono block bg-white p-1.5 rounded mt-0.5">{c.setup_command}</code>
                            </div>
                          )}
                          {c.env_vars?.length > 0 && (
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              {c.env_vars.map((ev, i) => (
                                <code key={i} className="text-[10px] bg-white px-1.5 py-0.5 rounded font-mono text-indigo-600">{ev}</code>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Test Steps Runbook */}
              <div className="card p-5">
                <h4 className="text-sm font-semibold text-fg-navy mb-3 uppercase tracking-wider">
                  Test Steps ({playbookTcData.length} test case{playbookTcData.length !== 1 ? 's' : ''})
                </h4>
                {playbookTcData.length === 0 ? (
                  <p className="text-sm text-fg-mid py-4 text-center">No test cases linked to this plan.</p>
                ) : (
                  <div className="space-y-4">
                    {playbookTcData.map((tc, ti) => (
                      <div key={tc.id} className="border border-gray-200 rounded-lg overflow-hidden">
                        <div className="px-4 py-3 bg-gray-50 flex items-center gap-3">
                          <span className="w-7 h-7 rounded-full bg-fg-teal text-white text-xs font-bold flex items-center justify-center">{ti + 1}</span>
                          <div className="flex-1">
                            <span className="text-sm font-mono font-semibold text-fg-dark">{tc.test_case_id}</span>
                            <span className="text-sm text-fg-mid ml-2">{tc.title}</span>
                          </div>
                          <span className="badge badge-gray text-xs">{tc.execution_type}</span>
                          <span className="badge badge-gray text-xs">{tc.priority}</span>
                        </div>
                        {(tc.test_steps || []).length > 0 && (
                          <div className="px-4 py-3 space-y-3">
                            {tc.test_steps.map((step, si) => (
                              <div key={si} className="flex gap-3">
                                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center mt-0.5">
                                  {step.step_number || si + 1}
                                </span>
                                <div className="flex-1 text-sm">
                                  <p className="text-fg-dark">{step.action}</p>
                                  <p className="text-fg-mid text-xs mt-0.5">Expected: {step.expected_result}</p>
                                  {/* Structured spec details */}
                                  {(step.step_type || step.tool_name || step.method || step.sql_script) && (
                                    <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px]">
                                      {step.step_type && <span className="bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-semibold uppercase">{step.step_type}</span>}
                                      {step.connection_ref && <span className="bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-mono">{step.connection_ref}</span>}
                                      {step.tool_name && <span className="bg-green-50 text-green-700 px-1.5 py-0.5 rounded font-mono">{step.tool_name}</span>}
                                      {step.method && <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-semibold">{step.method} {step.endpoint || ''}</span>}
                                    </div>
                                  )}
                                  {step.tool_params && (
                                    <pre className="mt-1 text-[11px] font-mono bg-gray-50 p-2 rounded text-fg-mid overflow-x-auto">
                                      {JSON.stringify(step.tool_params, null, 2)}
                                    </pre>
                                  )}
                                  {step.sql_script && (
                                    <pre className="mt-1 text-[11px] font-mono bg-gray-50 p-2 rounded text-fg-mid overflow-x-auto">
                                      {step.sql_script}
                                    </pre>
                                  )}
                                  {step.assertions?.length > 0 && (
                                    <div className="mt-1.5">
                                      <span className="text-[10px] font-semibold text-fg-mid uppercase">Assertions:</span>
                                      <div className="flex flex-wrap gap-1 mt-0.5">
                                        {step.assertions.map((a, ai) => (
                                          <span key={ai} className="text-[10px] bg-amber-50 text-amber-800 px-1.5 py-0.5 rounded font-mono">
                                            {a.type}{a.path ? `:${a.path}` : ''}{a.expected !== undefined ? `=${a.expected}` : ''}{a.value !== undefined ? `${a.operator || '='}${a.value}` : ''}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Post-conditions */}
              {ec.post_conditions?.length > 0 && (
                <div className="card p-5">
                  <h4 className="text-sm font-semibold text-fg-navy mb-3 uppercase tracking-wider">Post-Conditions</h4>
                  <ol className="list-decimal list-inside space-y-1.5 text-sm text-fg-dark">
                    {ec.post_conditions.map((p, i) => <li key={i}>{p}</li>)}
                  </ol>
                </div>
              )}

              {/* Empty state when no execution_config */}
              {!ec.environment && !ec.required_env_vars?.length && !ec.prerequisites?.length && !ec.post_conditions?.length && Object.keys(connections).length === 0 && (
                <div className="card p-5 text-center">
                  <p className="text-fg-mid text-sm">
                    No execution config set for this plan. Edit the test plan to add environment details, prerequisites, and required env vars.
                    Add connections to the project's App Profile to see them here.
                  </p>
                </div>
              )}
            </div>
          );
        })()}
      </div>}

      {/* Proof Viewer Modal */}
      <ProofViewer proof={selectedProof} visible={!!selectedProof} onClose={() => setSelectedProof(null)} />
    </div>
  );
}

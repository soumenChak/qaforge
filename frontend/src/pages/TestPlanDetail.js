import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { testCasesAPI, testPlansAPI, executionsAPI } from '../services/api';
import Breadcrumb from '../components/Breadcrumb';
import { CheckCircleIcon, XCircleIcon, ClockIcon, ChevronDownIcon, ChevronUpIcon, PlusIcon } from '@heroicons/react/24/outline';

const STATUS_CHIP = { draft: 'badge-gray', reviewed: 'bg-blue-100 text-blue-800', approved: 'badge-green', executed: 'bg-orange-100 text-orange-800', passed: 'badge-green', failed: 'badge-red' };
const CP_TYPES = ['test_case_review', 'execution_review', 'sign_off'];
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
  // Checkpoints
  const [checkpoints, setCheckpoints] = useState([]);
  const [cpLoading, setCpLoading] = useState(false);
  const [showAddCp, setShowAddCp] = useState(false);
  const [newCpType, setNewCpType] = useState(CP_TYPES[0]);
  const [cpAdding, setCpAdding] = useState(false);
  const [reviewingCpId, setReviewingCpId] = useState(null);
  const [cpReviewComment, setCpReviewComment] = useState('');
  // Traceability & Summary
  const [traceability, setTraceability] = useState(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [sumLoading, setSumLoading] = useState(false);

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
  const loadCP = useCallback(() => load(() => testPlansAPI.listCheckpoints(projectId, planId), setCheckpoints, setCpLoading), [projectId, planId, load]);
  const loadTrace = useCallback(() => load(() => testPlansAPI.getTraceability(projectId, planId), setTraceability, setTraceLoading), [projectId, planId, load]);
  const loadSum = useCallback(() => load(() => testPlansAPI.getSummary(projectId, planId), setSummary, setSumLoading), [projectId, planId, load]);

  useEffect(() => { loadPlan(); }, [loadPlan]);
  useEffect(() => { if (activeTab === 'test_cases') loadTC(); }, [activeTab, loadTC]);
  useEffect(() => { if (activeTab === 'executions') loadExec(); }, [activeTab, loadExec]);
  useEffect(() => { if (activeTab === 'checkpoints') loadCP(); }, [activeTab, loadCP]);
  useEffect(() => { if (activeTab === 'traceability') loadTrace(); }, [activeTab, loadTrace]);
  useEffect(() => { if (activeTab === 'summary') loadSum(); }, [activeTab, loadSum]);

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

  const addCheckpoint = async () => {
    setCpAdding(true);
    try { await testPlansAPI.createCheckpoint(projectId, planId, { type: newCpType }); setShowAddCp(false); loadCP(); }
    catch (e) { alert(e.response?.data?.detail || 'Failed to add checkpoint.'); }
    finally { setCpAdding(false); }
  };

  const cpReview = async (id, status) => {
    try { await testPlansAPI.reviewCheckpoint(projectId, id, { status, comment: cpReviewComment }); setReviewingCpId(null); setCpReviewComment(''); loadCP(); }
    catch (e) { alert(e.response?.data?.detail || 'Checkpoint review failed.'); }
  };

  // ── Guards ──
  if (loading) return <div className="page-container"><Spinner /></div>;
  if (!plan) return <div className="page-container"><p className="text-fg-mid">Test plan not found.</p><button onClick={() => navigate(-1)} className="btn-secondary mt-4">Go Back</button></div>;

  const tabs = [
    { key: 'test_cases', label: `Test Cases (${testCases.length})` },
    { key: 'executions', label: `Executions (${executions.length})` },
    { key: 'checkpoints', label: `Checkpoints (${checkpoints.length})` },
    { key: 'traceability', label: 'Traceability' },
    { key: 'summary', label: 'Summary' },
  ];

  const covPct = traceability?.coverage_percentage ?? 0;
  const covTextCls = covPct >= 80 ? 'text-green-600' : covPct >= 50 ? 'text-yellow-600' : 'text-red-600';
  const covBarCls = covPct >= 80 ? 'bg-green-500' : covPct >= 50 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <Breadcrumb items={[{ label: 'Projects', to: '/projects' }, { label: plan.project_name || 'Project', to: `/projects/${projectId}` }, { label: plan.name || 'Test Plan' }]} />
        <h1 className="text-2xl font-bold text-fg-navy mt-2">{plan.name}</h1>
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
                  <td className="px-4 py-3 text-sm text-fg-mid">{ex.duration != null ? `${ex.duration}s` : '-'}</td>
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
                  {ex.proof_artifacts?.length > 0 ? (<div>
                    <p className="text-xs font-semibold text-fg-mid mb-2 uppercase tracking-wider">Proof Artifacts</p>
                    <div className="flex flex-wrap gap-2">
                      {ex.proof_artifacts.map((a, i) => <div key={i} className="card-static px-3 py-2 text-xs">
                        <span className="font-medium text-fg-dark">{a.title || 'Untitled'}</span>
                        <span className="badge badge-gray ml-2">{a.type}</span>
                      </div>)}
                    </div>
                  </div>) : <p className="text-xs text-fg-mid">No proof artifacts for this execution.</p>}
                </td></tr>}
              </React.Fragment>)}
            </tbody>
          </table></div>
        )}
      </div>}

      {/* ── Checkpoints ── */}
      {activeTab === 'checkpoints' && <div className="animate-fade-in">
        <div className="flex items-center gap-3 mb-4">
          {showAddCp ? (<div className="flex items-center gap-2">
            <select value={newCpType} onChange={e => setNewCpType(e.target.value)} className="input-field text-sm w-48">
              {CP_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
            </select>
            <button onClick={addCheckpoint} disabled={cpAdding} className="btn-primary text-sm">{cpAdding ? 'Adding...' : 'Add'}</button>
            <button onClick={() => setShowAddCp(false)} className="btn-ghost text-sm">Cancel</button>
          </div>) : (
            <button onClick={() => setShowAddCp(true)} className="btn-secondary flex items-center gap-2 text-sm"><PlusIcon className="w-4 h-4" /> Add Checkpoint</button>
          )}
        </div>
        {cpLoading ? <Spinner /> : !checkpoints.length ? <p className="text-fg-mid text-sm py-8 text-center">No checkpoints defined.</p> : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {checkpoints.map(cp => <div key={cp.id} className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-fg-navy capitalize">{cp.type?.replace(/_/g, ' ')}</span>
                <span className={`badge ${CP_STATUS[cp.status] || 'badge-gray'}`}>{cp.status}</span>
              </div>
              {cp.reviewer && <p className="text-xs text-fg-mid mb-1">Reviewer: {cp.reviewer}</p>}
              {cp.reviewed_at && <p className="text-xs text-fg-mid mb-3">Reviewed: {new Date(cp.reviewed_at).toLocaleString()}</p>}
              {cp.comment && <p className="text-xs text-fg-mid italic mb-3">"{cp.comment}"</p>}
              {reviewingCpId === cp.id ? (
                <div className="flex flex-col gap-2 mt-2">
                  <input type="text" placeholder="Comment (optional)" value={cpReviewComment} onChange={e => setCpReviewComment(e.target.value)} className="input-field text-xs" />
                  <div className="flex gap-1 flex-wrap">
                    <button onClick={() => cpReview(cp.id, 'approved')} className="btn-primary text-xs px-2 py-1">Approve</button>
                    <button onClick={() => cpReview(cp.id, 'rejected')} className="btn-danger text-xs px-2 py-1">Reject</button>
                    <button onClick={() => cpReview(cp.id, 'needs_rework')} className="btn-secondary text-xs px-2 py-1">Needs Rework</button>
                    <button onClick={() => { setReviewingCpId(null); setCpReviewComment(''); }} className="btn-ghost text-xs px-2 py-1">Cancel</button>
                  </div>
                </div>
              ) : <button onClick={() => setReviewingCpId(cp.id)} className="btn-secondary text-xs mt-2">Review</button>}
            </div>)}
          </div>
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
    </div>
  );
}

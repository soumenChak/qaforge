import React, { useState, useEffect, useCallback } from 'react';
import { reviewsAPI, testCasesAPI, executionsAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import ProofViewer from '../components/ProofViewer';

const STATUS_COLORS = {
  passed: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
  error: 'bg-orange-100 text-orange-700',
  skipped: 'bg-gray-100 text-gray-600',
  blocked: 'bg-yellow-100 text-yellow-700',
};

const PRIORITY_COLORS = {
  P1: 'bg-red-100 text-red-700',
  P2: 'bg-orange-100 text-orange-700',
  P3: 'bg-blue-100 text-blue-700',
  P4: 'bg-gray-100 text-gray-600',
};

export default function ReviewQueue() {
  const [tab, setTab] = useState('test_cases');
  const [data, setData] = useState({ test_cases: [], executions: [], counts: { tc_pending: 0, exec_pending: 0 } });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedTCs, setSelectedTCs] = useState(new Set());
  const [selectedExecs, setSelectedExecs] = useState(new Set());
  const [expandedTC, setExpandedTC] = useState(null);
  const [expandedExec, setExpandedExec] = useState(null);
  const [proofArtifact, setProofArtifact] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await reviewsAPI.getPending();
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load pending reviews');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleBulkApproveTC = async () => {
    if (selectedTCs.size === 0) return;
    try {
      // For each selected TC, update status to "reviewed"
      for (const tcId of selectedTCs) {
        const tc = data.test_cases.find(t => t.id === tcId);
        if (tc) {
          await testCasesAPI.update(tc.project_id, tcId, { status: 'reviewed' });
        }
      }
      setSelectedTCs(new Set());
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve test cases');
    }
  };

  const handleBulkRejectTC = async () => {
    if (selectedTCs.size === 0) return;
    try {
      for (const tcId of selectedTCs) {
        const tc = data.test_cases.find(t => t.id === tcId);
        if (tc) {
          await testCasesAPI.update(tc.project_id, tcId, { status: 'deprecated' });
        }
      }
      setSelectedTCs(new Set());
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject test cases');
    }
  };

  const handleBulkApproveExec = async () => {
    if (selectedExecs.size === 0) return;
    try {
      for (const execId of selectedExecs) {
        const exec = data.executions.find(e => e.id === execId);
        if (exec) {
          await executionsAPI.review(exec.project_id, execId, { review_status: 'approved' });
        }
      }
      setSelectedExecs(new Set());
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve executions');
    }
  };

  const handleApproveAllPassed = async () => {
    const passedExecs = data.executions.filter(e => e.status === 'passed');
    if (passedExecs.length === 0) return;
    try {
      for (const exec of passedExecs) {
        await executionsAPI.review(exec.project_id, exec.id, { review_status: 'approved' });
      }
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve passed executions');
    }
  };

  const toggleSelectTC = (id) => {
    setSelectedTCs(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectExec = (id) => {
    setSelectedExecs(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const selectAllTCs = () => {
    if (selectedTCs.size === data.test_cases.length) {
      setSelectedTCs(new Set());
    } else {
      setSelectedTCs(new Set(data.test_cases.map(tc => tc.id)));
    }
  };

  const selectAllExecs = () => {
    if (selectedExecs.size === data.executions.length) {
      setSelectedExecs(new Set());
    } else {
      setSelectedExecs(new Set(data.executions.map(e => e.id)));
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="flex justify-center py-20">
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
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Review Queue</h1>
          <p className="text-sm text-fg-mid mt-1">
            {data.counts.tc_pending} test cases and {data.counts.exec_pending} executions pending review
          </p>
        </div>
        <button onClick={loadData} className="btn-secondary text-sm">Refresh</button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-white rounded-lg p-1 shadow-sm border border-fg-border w-fit">
        <button
          onClick={() => setTab('test_cases')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            tab === 'test_cases'
              ? 'bg-fg-teal text-white shadow-sm'
              : 'text-fg-mid hover:text-fg-dark'
          }`}
        >
          Test Cases ({data.counts.tc_pending})
        </button>
        <button
          onClick={() => setTab('executions')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            tab === 'executions'
              ? 'bg-fg-teal text-white shadow-sm'
              : 'text-fg-mid hover:text-fg-dark'
          }`}
        >
          Executions ({data.counts.exec_pending})
        </button>
      </div>

      {/* Test Cases Tab */}
      {tab === 'test_cases' && (
        <div className="card-static">
          {/* Bulk actions */}
          {selectedTCs.size > 0 && (
            <div className="flex items-center gap-3 p-3 bg-fg-teal/5 border-b border-fg-border">
              <span className="text-sm text-fg-dark font-medium">{selectedTCs.size} selected</span>
              <button onClick={handleBulkApproveTC} className="btn-primary text-xs py-1 px-3">Approve</button>
              <button onClick={handleBulkRejectTC} className="btn-danger text-xs py-1 px-3">Reject</button>
            </div>
          )}

          {data.test_cases.length === 0 ? (
            <div className="p-12 text-center text-fg-mid">
              <p className="text-lg font-medium">No pending test case reviews</p>
              <p className="text-sm mt-1">All test cases have been reviewed</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-fg-border bg-fg-gray/50">
                  <th className="p-3 text-left w-10">
                    <input
                      type="checkbox"
                      checked={selectedTCs.size === data.test_cases.length && data.test_cases.length > 0}
                      onChange={selectAllTCs}
                      className="rounded border-gray-300"
                    />
                  </th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Project</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">TC ID</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Title</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Priority</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Category</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Source</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.test_cases.map((tc) => (
                  <React.Fragment key={tc.id}>
                    <tr
                      className="border-b border-fg-border hover:bg-fg-gray/30 cursor-pointer transition-colors"
                      onClick={() => setExpandedTC(expandedTC === tc.id ? null : tc.id)}
                    >
                      <td className="p-3" onClick={e => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedTCs.has(tc.id)}
                          onChange={() => toggleSelectTC(tc.id)}
                          className="rounded border-gray-300"
                        />
                      </td>
                      <td className="p-3 text-sm font-medium text-fg-dark">{tc.project_name}</td>
                      <td className="p-3 text-sm font-mono text-fg-mid">{tc.test_case_id}</td>
                      <td className="p-3 text-sm text-fg-dark max-w-xs truncate">{tc.title}</td>
                      <td className="p-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLORS[tc.priority] || 'bg-gray-100 text-gray-600'}`}>
                          {tc.priority}
                        </span>
                      </td>
                      <td className="p-3 text-sm text-fg-mid capitalize">{tc.category}</td>
                      <td className="p-3 text-sm text-fg-mid">{tc.source === 'ai_generated' ? 'AI' : tc.source}</td>
                      <td className="p-3 text-sm text-fg-mid">
                        {tc.created_at ? new Date(tc.created_at).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                    {expandedTC === tc.id && (
                      <tr>
                        <td colSpan={8} className="p-4 bg-fg-gray/20">
                          <div className="text-sm text-fg-dark">
                            <p className="font-medium mb-2">Expand to view full test case details in Project Detail</p>
                            <a
                              href={`/projects/${tc.project_id}`}
                              className="text-fg-teal hover:underline"
                            >
                              Open in Project &rarr;
                            </a>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Executions Tab */}
      {tab === 'executions' && (
        <div className="card-static">
          {/* Bulk actions */}
          <div className="flex items-center gap-3 p-3 border-b border-fg-border">
            {selectedExecs.size > 0 && (
              <>
                <span className="text-sm text-fg-dark font-medium">{selectedExecs.size} selected</span>
                <button onClick={handleBulkApproveExec} className="btn-primary text-xs py-1 px-3">Approve</button>
              </>
            )}
            {data.executions.filter(e => e.status === 'passed').length > 0 && (
              <button onClick={handleApproveAllPassed} className="btn-secondary text-xs py-1 px-3 ml-auto">
                Approve All Passed ({data.executions.filter(e => e.status === 'passed').length})
              </button>
            )}
          </div>

          {data.executions.length === 0 ? (
            <div className="p-12 text-center text-fg-mid">
              <p className="text-lg font-medium">No pending execution reviews</p>
              <p className="text-sm mt-1">All executions have been reviewed</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-fg-border bg-fg-gray/50">
                  <th className="p-3 text-left w-10">
                    <input
                      type="checkbox"
                      checked={selectedExecs.size === data.executions.length && data.executions.length > 0}
                      onChange={selectAllExecs}
                      className="rounded border-gray-300"
                    />
                  </th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Project</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Test Case</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Status</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Result</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Duration</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Agent</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Proofs</th>
                  <th className="p-3 text-left text-xs font-semibold text-fg-mid uppercase">Executed</th>
                </tr>
              </thead>
              <tbody>
                {data.executions.map((exec) => (
                  <tr
                    key={exec.id}
                    className="border-b border-fg-border hover:bg-fg-gray/30 cursor-pointer transition-colors"
                    onClick={() => setExpandedExec(expandedExec === exec.id ? null : exec.id)}
                  >
                    <td className="p-3" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedExecs.has(exec.id)}
                        onChange={() => toggleSelectExec(exec.id)}
                        className="rounded border-gray-300"
                      />
                    </td>
                    <td className="p-3 text-sm font-medium text-fg-dark">{exec.project_name}</td>
                    <td className="p-3 text-sm text-fg-dark">
                      <span className="font-mono text-fg-mid">{exec.test_case_id}</span>
                      {exec.test_case_title && (
                        <span className="block text-xs text-fg-mid truncate max-w-xs">{exec.test_case_title}</span>
                      )}
                    </td>
                    <td className="p-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[exec.status] || 'bg-gray-100'}`}>
                        {exec.status}
                      </span>
                    </td>
                    <td className="p-3 text-sm text-fg-mid max-w-xs truncate">{exec.actual_result || '-'}</td>
                    <td className="p-3 text-sm text-fg-mid">
                      {exec.duration_ms ? `${exec.duration_ms}ms` : '-'}
                    </td>
                    <td className="p-3 text-sm text-fg-mid">{exec.executed_by}</td>
                    <td className="p-3 text-sm text-fg-mid">{exec.proof_count || 0}</td>
                    <td className="p-3 text-sm text-fg-mid">
                      {exec.executed_at ? new Date(exec.executed_at).toLocaleDateString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Proof Viewer Modal */}
      {proofArtifact && (
        <ProofViewer
          artifact={proofArtifact}
          onClose={() => setProofArtifact(null)}
        />
      )}
    </div>
  );
}

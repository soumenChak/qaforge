import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { testPlansAPI, projectsAPI } from '../services/api';
import Breadcrumb from '../components/Breadcrumb';
import {
  PlusIcon,
  XMarkIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline';

const TYPE_LABELS = { sit: 'SIT', uat: 'UAT', regression: 'Regression', smoke: 'Smoke', migration: 'Migration', custom: 'Custom' };
const TYPE_COLORS = { sit: 'badge-teal', uat: 'badge-green', regression: 'badge-yellow', smoke: 'badge-gray', migration: 'badge-red', custom: 'badge-gray' };
const STATUS_COLORS = { draft: 'badge-gray', active: 'badge-teal', in_progress: 'badge-yellow', completed: 'badge-green', archived: 'badge-gray' };

export default function TestPlans() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  // Create form state
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newType, setNewType] = useState('sit');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [projectRes, plansRes] = await Promise.all([
        projectsAPI.getById(projectId),
        testPlansAPI.list(projectId),
      ]);
      setProject(projectRes.data);
      setPlans(plansRes.data);
    } catch (err) {
      console.error('Failed to load test plans:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) {
      setCreateError('Plan name is required.');
      return;
    }
    setCreating(true);
    setCreateError('');
    try {
      await testPlansAPI.create(projectId, {
        name: newName.trim(),
        description: newDescription.trim() || null,
        plan_type: newType,
      });
      setShowModal(false);
      resetForm();
      loadData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setCreateError(detail.map((d) => d.msg || String(d)).join('; '));
      } else if (typeof detail === 'string') {
        setCreateError(detail);
      } else {
        setCreateError('Failed to create test plan.');
      }
    } finally {
      setCreating(false);
    }
  };

  const resetForm = () => { setNewName(''); setNewDescription(''); setNewType('sit'); setCreateError(''); };

  const getPassRate = (plan) => (plan.total_executed || 0) === 0
    ? null : Math.round(((plan.passed_count || 0) / plan.total_executed) * 100);

  const getProgress = (plan) => (plan.test_case_count || 0) === 0
    ? 0 : Math.round(((plan.passed_count || 0) / plan.test_case_count) * 100);

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

  return (
    <div className="page-container">
      <Breadcrumb items={[
        { label: 'Projects', to: '/projects' },
        { label: project?.name || 'Project', to: `/projects/${projectId}` },
        { label: 'Test Plans' },
      ]} />

      {/* Header */}
      <div className="section-header">
        <div>
          <h1 className="text-2xl font-bold text-fg-navy">Test Plans</h1>
          <p className="text-sm text-fg-mid mt-1">
            {plans.length} plan{plans.length !== 1 ? 's' : ''} for {project?.name || 'this project'}
          </p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2">
          <PlusIcon className="w-4 h-4" />
          Create Test Plan
        </button>
      </div>

      {/* Plans table */}
      {plans.length === 0 ? (
        <div className="card-static p-12 text-center">
          <ClipboardDocumentListIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-fg-mid mb-4">No test plans yet.</p>
          <button onClick={() => setShowModal(true)} className="btn-primary">
            Create Your First Test Plan
          </button>
        </div>
      ) : (
        <div className="card-static table-container">
          <table className="min-w-full">
            <thead>
              <tr className="table-header">
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3 text-center">Test Cases</th>
                <th className="px-5 py-3">Pass Rate</th>
                <th className="px-5 py-3">Progress</th>
                <th className="px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="bg-white">
              {plans.map((plan) => {
                const passRate = getPassRate(plan);
                const progress = getProgress(plan);

                return (
                  <tr
                    key={plan.id}
                    className="table-row cursor-pointer"
                    onClick={() => navigate(`/projects/${projectId}/test-plans/${plan.id}`)}
                  >
                    <td className="px-5 py-3.5">
                      <span className="text-sm font-semibold text-fg-teal hover:text-fg-tealDark">
                        {plan.name}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`badge ${TYPE_COLORS[plan.plan_type] || 'badge-gray'}`}>
                        {TYPE_LABELS[plan.plan_type] || plan.plan_type}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`badge ${STATUS_COLORS[plan.status] || 'badge-gray'}`}>
                        {(plan.status || 'draft').replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-center text-sm text-fg-dark font-medium">
                      {plan.test_case_count || 0}
                    </td>
                    <td className="px-5 py-3.5">
                      {passRate !== null ? (
                        <span className={`text-sm font-semibold ${passRate >= 70 ? 'text-green-600' : passRate >= 40 ? 'text-yellow-600' : 'text-red-600'}`}>
                          {passRate}%
                          <span className="text-xs text-fg-mid font-normal ml-1">
                            ({plan.passed_count}/{plan.total_executed})
                          </span>
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">--</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden" style={{ minWidth: 60 }}>
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${
                              progress >= 70 ? 'bg-green-500' : progress >= 40 ? 'bg-yellow-500' : 'bg-red-400'
                            }`}
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                        <span className="text-xs text-fg-mid w-8 text-right">{progress}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-xs text-gray-400">
                      {new Date(plan.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Test Plan Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-fg-navy">New Test Plan</h2>
                <button onClick={() => { setShowModal(false); resetForm(); }} className="text-fg-mid hover:text-fg-dark">
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              {createError && (
                <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {createError}
                </div>
              )}

              <form onSubmit={handleCreate} className="space-y-5">
                <div>
                  <label className="label">Plan Name</label>
                  <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g., Sprint 12 Regression Suite"
                    className="input-field"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="label">Plan Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="input-field"
                  >
                    {Object.entries(TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="label">Description</label>
                  <textarea
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                    placeholder="Brief description of the test plan scope..."
                    rows={3}
                    className="input-field"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => { setShowModal(false); resetForm(); }}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                  <button type="submit" disabled={creating} className="btn-primary">
                    {creating ? 'Creating...' : 'Create Plan'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

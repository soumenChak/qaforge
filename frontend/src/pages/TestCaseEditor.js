import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { testCasesAPI } from '../services/api';
import RatingWidget from '../components/RatingWidget';
import {
  ArrowLeftIcon,
  TrashIcon,
  PlusIcon,
  ArrowsUpDownIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

export default function TestCaseEditor() {
  const { id: projectId, tcId } = useParams();
  const navigate = useNavigate();

  const [tc, setTc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Form fields
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [preconditions, setPreconditions] = useState('');
  const [expectedResult, setExpectedResult] = useState('');
  const [priority, setPriority] = useState('P2');
  const [category, setCategory] = useState('functional');
  const [status, setStatus] = useState('draft');
  const [testSteps, setTestSteps] = useState([]);

  const loadTestCase = useCallback(async () => {
    try {
      const res = await testCasesAPI.getById(projectId, tcId);
      const data = res.data;
      setTc(data);
      setTitle(data.title || '');
      setDescription(data.description || '');
      setPreconditions(data.preconditions || '');
      setExpectedResult(data.expected_result || '');
      setPriority(data.priority || 'P2');
      setCategory(data.category || 'functional');
      setStatus(data.status || 'draft');
      setTestSteps(data.test_steps || []);
    } catch (err) {
      setError('Failed to load test case.');
    } finally {
      setLoading(false);
    }
  }, [projectId, tcId]);

  useEffect(() => { loadTestCase(); }, [loadTestCase]);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccessMsg('');
    try {
      const payload = {
        title,
        description: description || null,
        preconditions: preconditions || null,
        expected_result: expectedResult || null,
        priority,
        category,
        status,
        test_steps: testSteps.map((s, i) => ({
          step_number: i + 1,
          action: s.action || '',
          expected_result: s.expected_result || '',
        })),
      };
      const res = await testCasesAPI.update(projectId, tcId, payload);
      setTc(res.data);
      setSuccessMsg('Test case saved successfully.');
      setTimeout(() => setSuccessMsg(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete test case ${tc?.test_case_id}? This cannot be undone.`)) return;
    try {
      await testCasesAPI.delete(projectId, tcId);
      navigate(`/projects/${projectId}`);
    } catch (err) {
      setError('Failed to delete test case.');
    }
  };

  const handleRate = async ({ rating, feedback_text }) => {
    try {
      const res = await testCasesAPI.rate(projectId, tcId, { rating, feedback_text });
      setTc(res.data);
    } catch (err) {
      alert('Failed to submit rating.');
    }
  };

  // Step management
  const addStep = () => {
    setTestSteps([...testSteps, { step_number: testSteps.length + 1, action: '', expected_result: '' }]);
  };

  const removeStep = (index) => {
    setTestSteps(testSteps.filter((_, i) => i !== index));
  };

  const updateStep = (index, field, value) => {
    const updated = [...testSteps];
    updated[index] = { ...updated[index], [field]: value };
    setTestSteps(updated);
  };

  const moveStep = (index, direction) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= testSteps.length) return;
    const updated = [...testSteps];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    setTestSteps(updated);
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

  if (!tc) {
    return (
      <div className="page-container">
        <div className="card-static p-8 text-center">
          <p className="text-fg-mid">{error || 'Test case not found.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container max-w-4xl">
      {/* Back */}
      <button
        onClick={() => navigate(`/projects/${projectId}`)}
        className="text-sm text-fg-mid hover:text-fg-dark mb-4 inline-flex items-center gap-1"
      >
        <ArrowLeftIcon className="w-4 h-4" />
        Back to Project
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-mono font-bold text-fg-tealDark">{tc.test_case_id}</span>
            {tc.source === 'ai_generated' && (
              <span className="badge badge-teal text-xs">AI Generated</span>
            )}
          </div>
          <h1 className="text-xl font-bold text-fg-navy">{tc.title}</h1>
        </div>
        <button
          onClick={handleDelete}
          className="btn-danger text-sm flex items-center gap-2"
        >
          <TrashIcon className="w-4 h-4" />
          Delete
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 animate-fade-in">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700 animate-fade-in">
          {successMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main form -- 2/3 width */}
        <div className="lg:col-span-2 space-y-5">
          <div className="card-static p-5">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">Details</h3>

            <div className="space-y-4">
              <div>
                <label className="label">Title</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} className="input-field" />
              </div>

              <div>
                <label className="label">Description</label>
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="input-field" />
              </div>

              <div>
                <label className="label">Preconditions</label>
                <textarea value={preconditions} onChange={(e) => setPreconditions(e.target.value)} rows={2} className="input-field" />
              </div>

              <div>
                <label className="label">Expected Result</label>
                <textarea value={expectedResult} onChange={(e) => setExpectedResult(e.target.value)} rows={2} className="input-field" />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="label">Priority</label>
                  <select value={priority} onChange={(e) => setPriority(e.target.value)} className="input-field">
                    <option value="P1">P1 - Critical</option>
                    <option value="P2">P2 - High</option>
                    <option value="P3">P3 - Medium</option>
                    <option value="P4">P4 - Low</option>
                  </select>
                </div>
                <div>
                  <label className="label">Category</label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className="input-field">
                    <option value="functional">Functional</option>
                    <option value="integration">Integration</option>
                    <option value="regression">Regression</option>
                    <option value="smoke">Smoke</option>
                    <option value="e2e">End-to-End</option>
                  </select>
                </div>
                <div>
                  <label className="label">Status</label>
                  <select value={status} onChange={(e) => setStatus(e.target.value)} className="input-field">
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="passed">Passed</option>
                    <option value="failed">Failed</option>
                    <option value="blocked">Blocked</option>
                    <option value="deprecated">Deprecated</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Test Steps */}
          <div className="card-static p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider">
                Test Steps ({testSteps.length})
              </h3>
              <button onClick={addStep} className="btn-ghost text-sm flex items-center gap-1">
                <PlusIcon className="w-4 h-4" />
                Add Step
              </button>
            </div>

            {testSteps.length === 0 ? (
              <p className="text-sm text-fg-mid text-center py-4">
                No test steps. Click "Add Step" to begin.
              </p>
            ) : (
              <div className="space-y-3">
                {testSteps.map((step, idx) => (
                  <div key={idx} className="flex gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className="flex flex-col items-center gap-1 flex-shrink-0 pt-1">
                      <span className="w-7 h-7 rounded-full bg-fg-teal text-white text-xs font-bold flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <button
                        onClick={() => moveStep(idx, -1)}
                        disabled={idx === 0}
                        className="text-gray-300 hover:text-fg-mid disabled:opacity-30"
                        title="Move up"
                      >
                        <ArrowsUpDownIcon className="w-3.5 h-3.5 rotate-180" />
                      </button>
                      <button
                        onClick={() => moveStep(idx, 1)}
                        disabled={idx === testSteps.length - 1}
                        className="text-gray-300 hover:text-fg-mid disabled:opacity-30"
                        title="Move down"
                      >
                        <ArrowsUpDownIcon className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="flex-1 space-y-2">
                      <div>
                        <label className="text-xs font-medium text-fg-mid">Action</label>
                        <textarea
                          value={step.action || ''}
                          onChange={(e) => updateStep(idx, 'action', e.target.value)}
                          rows={2}
                          className="input-field text-sm"
                          placeholder="What to do..."
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-fg-mid">Expected Result</label>
                        <textarea
                          value={step.expected_result || ''}
                          onChange={(e) => updateStep(idx, 'expected_result', e.target.value)}
                          rows={2}
                          className="input-field text-sm"
                          placeholder="What should happen..."
                        />
                      </div>
                    </div>
                    <button
                      onClick={() => removeStep(idx)}
                      className="text-gray-300 hover:text-red-500 flex-shrink-0 mt-1"
                      title="Remove step"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Save/Cancel */}
          <div className="flex justify-end gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}`)}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>

        {/* Sidebar -- 1/3 width */}
        <div className="space-y-5">
          {/* Rating card */}
          <div className="card-static p-5">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Quality Rating</h3>
            <RatingWidget
              value={tc.rating || 0}
              onSubmit={handleRate}
              size="lg"
            />
          </div>

          {/* Metadata card */}
          <div className="card-static p-5">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Metadata</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-fg-mid">Source</span>
                <span className="font-medium text-fg-dark capitalize">{tc.source?.replace(/_/g, ' ')}</span>
              </div>
              {tc.generated_by_model && (
                <div className="flex justify-between">
                  <span className="text-fg-mid">Model</span>
                  <span className="font-medium text-fg-dark">{tc.generated_by_model}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-fg-mid">Created</span>
                <span className="font-medium text-fg-dark">
                  {tc.created_at ? new Date(tc.created_at).toLocaleDateString() : '--'}
                </span>
              </div>
              {tc.updated_at && (
                <div className="flex justify-between">
                  <span className="text-fg-mid">Updated</span>
                  <span className="font-medium text-fg-dark">
                    {new Date(tc.updated_at).toLocaleDateString()}
                  </span>
                </div>
              )}
              {tc.domain_tags && tc.domain_tags.length > 0 && (
                <div className="pt-2">
                  <span className="text-fg-mid text-xs">Tags</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {tc.domain_tags.map((tag, i) => (
                      <span key={i} className="badge badge-gray text-xs">{tag}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

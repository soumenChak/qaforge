import React, { useState, useEffect, useCallback } from 'react';
import { templatesAPI } from '../services/api';
import {
  PlusIcon,
  XMarkIcon,
  TrashIcon,
  EyeIcon,
  PencilSquareIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import { DOMAIN_COLORS, DOMAIN_NAMES } from '../constants/domains';

const FORMAT_COLORS = {
  excel: 'bg-green-100 text-green-700',
  word: 'bg-blue-100 text-blue-700',
  json: 'bg-yellow-100 text-yellow-700',
};

export default function TemplateManager() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [preview, setPreview] = useState(null);

  // Create / Edit form
  const [editingId, setEditingId] = useState(null); // null = create mode, UUID = edit mode
  const [formName, setFormName] = useState('');
  const [formDomain, setFormDomain] = useState('mdm');
  const [formFormat, setFormFormat] = useState('excel');
  const [formColumns, setFormColumns] = useState({
    A: 'Test Case ID',
    B: 'Title',
    C: 'Description',
    D: 'Preconditions',
    E: 'Test Steps',
    F: 'Expected Result',
    G: 'Priority',
    H: 'Category',
    I: 'Status',
    J: 'Test Data',
  });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const loadTemplates = useCallback(async () => {
    try {
      const res = await templatesAPI.getAll();
      setTemplates(res.data);
    } catch (err) {
      console.error('Failed to load templates:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!formName.trim()) {
      setError('Template name is required.');
      return;
    }
    setCreating(true);
    setError('');
    try {
      await templatesAPI.create({
        name: formName.trim(),
        domain: formDomain,
        format: formFormat,
        column_mapping: formColumns,
      });
      setShowCreate(false);
      resetForm();
      loadTemplates();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create template.');
    } finally {
      setCreating(false);
    }
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!formName.trim()) {
      setError('Template name is required.');
      return;
    }
    setCreating(true);
    setError('');
    try {
      await templatesAPI.update(editingId, {
        name: formName.trim(),
        domain: formDomain,
        format: formFormat,
        column_mapping: formColumns,
      });
      setShowCreate(false);
      resetForm();
      loadTemplates();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update template.');
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = (template) => {
    setEditingId(template.id);
    setFormName(template.name);
    setFormDomain(template.domain);
    setFormFormat(template.format);
    setFormColumns(template.column_mapping || {
      A: 'Test Case ID',
      B: 'Title',
      C: 'Description',
      D: 'Preconditions',
      E: 'Test Steps',
      F: 'Expected Result',
      G: 'Priority',
      H: 'Category',
      I: 'Status',
      J: 'Test Data',
    });
    setError('');
    setShowCreate(true);
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete template "${name}"?`)) return;
    try {
      await templatesAPI.delete(id);
      loadTemplates();
    } catch (err) {
      alert('Failed to delete template.');
    }
  };

  const handlePreview = async (id) => {
    try {
      const res = await templatesAPI.preview(id);
      setPreview(res.data);
    } catch (err) {
      alert('Failed to load preview.');
    }
  };

  const resetForm = () => {
    setEditingId(null);
    setFormName('');
    setFormDomain('mdm');
    setFormFormat('excel');
    setFormColumns({
      A: 'Test Case ID',
      B: 'Title',
      C: 'Description',
      D: 'Preconditions',
      E: 'Test Steps',
      F: 'Expected Result',
      G: 'Priority',
      H: 'Category',
      I: 'Status',
      J: 'Test Data',
    });
    setError('');
  };

  const addColumn = () => {
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    const existingCols = Object.keys(formColumns);
    const nextLetter = letters[existingCols.length] || `Col${existingCols.length + 1}`;
    setFormColumns({ ...formColumns, [nextLetter]: '' });
  };

  const removeColumn = (col) => {
    const updated = { ...formColumns };
    delete updated[col];
    setFormColumns(updated);
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

  return (
    <div className="page-container">
      <div className="section-header">
        <div>
          <h1 className="text-2xl font-bold text-fg-navy">Templates</h1>
          <p className="text-sm text-fg-mid mt-1">Manage export templates for test case output</p>
        </div>
        <button onClick={() => { resetForm(); setShowCreate(true); }} className="btn-primary flex items-center gap-2">
          <PlusIcon className="w-4 h-4" />
          Create Template
        </button>
      </div>

      {/* Template cards */}
      {templates.length === 0 ? (
        <div className="card-static p-12 text-center">
          <DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-fg-mid mb-4">No templates yet.</p>
          <button onClick={() => { resetForm(); setShowCreate(true); }} className="btn-primary">Create Your First Template</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {templates.map((t) => (
            <div key={t.id} className="card overflow-hidden">
              <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
              <div className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-sm font-bold text-fg-navy truncate flex-1 mr-2">{t.name}</h3>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleEdit(t)}
                      className="text-gray-300 hover:text-fg-teal p-1"
                      title="Edit"
                    >
                      <PencilSquareIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handlePreview(t.id)}
                      className="text-gray-300 hover:text-fg-teal p-1"
                      title="Preview"
                    >
                      <EyeIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(t.id, t.name)}
                      className="text-gray-300 hover:text-red-500 p-1"
                      title="Delete"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="flex gap-2 mb-3">
                  <span className={`badge text-xs ${DOMAIN_COLORS[t.domain] || 'badge-gray'}`}>
                    {DOMAIN_NAMES[t.domain] || t.domain}
                  </span>
                  <span className={`badge text-xs ${FORMAT_COLORS[t.format] || 'badge-gray'}`}>
                    {t.format?.toUpperCase()}
                  </span>
                </div>

                <p className="text-xs text-fg-mid">
                  {t.column_mapping ? Object.keys(t.column_mapping).length : 0} columns configured
                </p>
                <p className="text-xs text-gray-400 mt-2">
                  Created {new Date(t.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview modal */}
      {preview && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto animate-slide-up">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-fg-navy">Template Preview: {preview.name}</h2>
                <button onClick={() => setPreview(null)} className="text-fg-mid hover:text-fg-dark">
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              <span className={`badge text-xs mb-4 inline-block ${FORMAT_COLORS[preview.format] || 'badge-gray'}`}>
                {preview.format?.toUpperCase()}
              </span>

              <h3 className="text-sm font-bold text-fg-navy mb-2">Column Mapping</h3>
              <div className="table-container">
                <table className="min-w-full">
                  <thead>
                    <tr className="table-header">
                      <th className="px-4 py-2">Column</th>
                      <th className="px-4 py-2">Maps To</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {preview.column_mapping && Object.entries(preview.column_mapping).map(([col, field]) => (
                      <tr key={col} className="text-sm">
                        <td className="px-4 py-2 font-mono font-bold text-fg-tealDark">{col}</td>
                        <td className="px-4 py-2 text-fg-dark">{field}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-fg-navy">
                  {editingId ? 'Edit Template' : 'Create Template'}
                </h2>
                <button onClick={() => { setShowCreate(false); resetForm(); }} className="text-fg-mid hover:text-fg-dark">
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {error}
                </div>
              )}

              <form onSubmit={editingId ? handleUpdate : handleCreate} className="space-y-5">
                <div>
                  <label className="label">Template Name</label>
                  <input
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g., MDM Standard Export"
                    className="input-field"
                    autoFocus
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Domain</label>
                    <select value={formDomain} onChange={(e) => setFormDomain(e.target.value)} className="input-field">
                      <option value="mdm">MDM</option>
                      <option value="ai">AI / GenAI</option>
                      <option value="data_eng">Data Engineering</option>
                      <option value="general">General</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">Format</label>
                    <select value={formFormat} onChange={(e) => setFormFormat(e.target.value)} className="input-field">
                      <option value="excel">Excel</option>
                      <option value="word">Word</option>
                      <option value="json">JSON</option>
                    </select>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="label mb-0">Column Configuration</label>
                    <button type="button" onClick={addColumn} className="text-xs text-fg-teal hover:text-fg-tealDark font-medium">
                      + Add Column
                    </button>
                  </div>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {Object.entries(formColumns).map(([col, field]) => (
                      <div key={col} className="flex items-center gap-3">
                        <span className="w-8 text-sm font-mono font-bold text-fg-tealDark">{col}</span>
                        <input
                          value={field}
                          onChange={(e) => setFormColumns({ ...formColumns, [col]: e.target.value })}
                          className="input-field flex-1 text-sm py-1.5"
                          placeholder="Column header name"
                        />
                        <button
                          type="button"
                          onClick={() => removeColumn(col)}
                          className="text-gray-300 hover:text-red-500 p-1"
                          title="Remove column"
                        >
                          <XMarkIcon className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => { setShowCreate(false); resetForm(); }} className="btn-secondary">
                    Cancel
                  </button>
                  <button type="submit" disabled={creating} className="btn-primary">
                    {creating
                      ? (editingId ? 'Saving...' : 'Creating...')
                      : (editingId ? 'Save Changes' : 'Create Template')
                    }
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

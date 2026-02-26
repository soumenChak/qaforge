import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { projectsAPI } from '../services/api';
import { DOMAIN_COLORS, DOMAIN_NAMES } from '../constants/domains';
import DomainSelector from '../components/DomainSelector';
import { PlusIcon, FunnelIcon, XMarkIcon, FolderIcon, EllipsisVerticalIcon, ArchiveBoxIcon, TrashIcon } from '@heroicons/react/24/outline';

const STATUS_COLORS = {
  active: 'badge-green',
  completed: 'badge-teal',
  archived: 'badge-gray',
};

const SUB_DOMAINS = {
  mdm: ['Reltio', 'Semarchy', 'Informatica MDM', 'Data Quality', 'Data Governance'],
  ai: ['GenAI / LLM', 'Machine Learning', 'Data Science', 'RAG Pipelines', 'NLP'],
  data_eng: ['Databricks', 'Snowflake', 'ETL Pipelines', 'Streaming', 'Data Lakehouse'],
};

export default function Projects() {
  const navigate = useNavigate();
  const location = useLocation();

  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterDomain, setFilterDomain] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [showModal, setShowModal] = useState(location.state?.openNewModal || false);

  // New project form
  const [newName, setNewName] = useState('');
  const [newDomain, setNewDomain] = useState('');
  const [newSubDomain, setNewSubDomain] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [menuOpen, setMenuOpen] = useState(null); // project id with open menu
  const [confirmDelete, setConfirmDelete] = useState(null); // project to confirm delete

  const loadProjects = useCallback(async () => {
    try {
      const params = {};
      if (filterDomain) params.domain = filterDomain;
      if (filterStatus) params.status = filterStatus;
      const res = await projectsAPI.getAll(params);
      setProjects(res.data);
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setLoading(false);
    }
  }, [filterDomain, filterStatus]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [menuOpen]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim() || !newDomain) {
      setCreateError('Name and domain are required.');
      return;
    }
    setCreating(true);
    setCreateError('');
    try {
      const res = await projectsAPI.create({
        name: newName.trim(),
        domain: newDomain,
        sub_domain: newSubDomain,
        description: newDescription.trim() || null,
      });
      setShowModal(false);
      resetForm();
      navigate(`/projects/${res.data.id}`);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setCreateError(detail.map((d) => d.msg || String(d)).join('; '));
      } else if (typeof detail === 'string') {
        setCreateError(detail);
      } else {
        setCreateError('Failed to create project.');
      }
    } finally {
      setCreating(false);
    }
  };

  const resetForm = () => {
    setNewName('');
    setNewDomain('');
    setNewSubDomain('');
    setNewDescription('');
    setCreateError('');
  };

  const handleArchive = async (e, project) => {
    e.stopPropagation();
    setMenuOpen(null);
    if (!window.confirm('Archive this project? It will be hidden from the main list.')) return;
    try {
      await projectsAPI.archive(project.id);
      loadProjects();
    } catch (err) {
      console.error('Failed to archive project:', err);
    }
  };

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!confirmDelete) return;
    try {
      await projectsAPI.delete(confirmDelete.id);
      setConfirmDelete(null);
      loadProjects();
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
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
      {/* Header */}
      <div className="section-header">
        <div>
          <h1 className="text-2xl font-bold text-fg-navy">Projects</h1>
          <p className="text-sm text-fg-mid mt-1">{projects.length} project{projects.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <FunnelIcon className="w-4 h-4 text-fg-mid" />
        <select
          value={filterDomain}
          onChange={(e) => setFilterDomain(e.target.value)}
          className="input-field w-auto"
        >
          <option value="">All Domains</option>
          <option value="mdm">MDM</option>
          <option value="ai">AI / GenAI</option>
          <option value="data_eng">Data Engineering</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="input-field w-auto"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="archived">Archived</option>
        </select>
        {(filterDomain || filterStatus) && (
          <button
            onClick={() => { setFilterDomain(''); setFilterStatus(''); }}
            className="text-xs text-fg-mid hover:text-fg-dark flex items-center gap-1"
          >
            <XMarkIcon className="w-3.5 h-3.5" />
            Clear
          </button>
        )}
      </div>

      {/* Project cards grid */}
      {projects.length === 0 ? (
        <div className="card-static p-12 text-center">
          <FolderIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-fg-mid mb-4">No projects found.</p>
          <button onClick={() => setShowModal(true)} className="btn-primary">
            Create Your First Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {projects.map((project) => {
            const passRate = (project.test_case_count || 0) > 0
              ? Math.round(((project.passed_count || 0) / project.test_case_count) * 100)
              : null;

            return (
              <div
                key={project.id}
                className="card cursor-pointer overflow-hidden"
                onClick={() => navigate(`/projects/${project.id}`)}
              >
                {/* Gradient accent */}
                <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />

                <div className="p-5">
                  {/* Title row */}
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-base font-bold text-fg-navy truncate flex-1 mr-3">
                      {project.name}
                    </h3>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`badge ${STATUS_COLORS[project.status] || 'badge-gray'}`}>
                        {project.status}
                      </span>
                      <div className="relative">
                        <button
                          onClick={(e) => { e.stopPropagation(); setMenuOpen(menuOpen === project.id ? null : project.id); }}
                          className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          <EllipsisVerticalIcon className="w-4 h-4" />
                        </button>
                        {menuOpen === project.id && (
                          <div className="absolute right-0 top-8 bg-white rounded-lg border border-gray-200 shadow-lg z-20 py-1 w-40">
                            {project.status !== 'archived' && (
                              <button
                                onClick={(e) => handleArchive(e, project)}
                                className="w-full text-left px-3 py-2 text-sm text-fg-dark hover:bg-gray-50 flex items-center gap-2 transition-colors"
                              >
                                <ArchiveBoxIcon className="w-4 h-4 text-gray-500" />
                                Archive
                              </button>
                            )}
                            <button
                              onClick={(e) => { e.stopPropagation(); setMenuOpen(null); setConfirmDelete(project); }}
                              className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                            >
                              <TrashIcon className="w-4 h-4" />
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Domain badges */}
                  <div className="flex items-center gap-2 mb-4">
                    <span className={`badge ${DOMAIN_COLORS[project.domain] || 'badge-gray'}`}>
                      {DOMAIN_NAMES[project.domain] || project.domain}
                    </span>
                    {project.sub_domain && (
                      <span className="badge badge-gray">{project.sub_domain}</span>
                    )}
                  </div>

                  {/* Stats row */}
                  <div className="flex items-center gap-5 text-sm text-fg-mid">
                    <span>
                      <strong className="text-fg-dark">{project.test_case_count || 0}</strong> test cases
                    </span>
                    <span>
                      <strong className="text-fg-dark">{project.requirement_count || 0}</strong> requirements
                    </span>
                    {passRate !== null && (
                      <span className={passRate >= 70 ? 'text-green-600' : 'text-orange-600'}>
                        <strong>{passRate}%</strong> passed
                      </span>
                    )}
                  </div>

                  {/* Created date */}
                  <p className="text-xs text-gray-400 mt-3">
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setConfirmDelete(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full animate-slide-up" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                  <TrashIcon className="w-5 h-5 text-red-600" />
                </div>
                <h2 className="text-lg font-bold text-fg-navy">Delete Project</h2>
              </div>
              <p className="text-sm text-fg-mid mb-1">
                Are you sure you want to permanently delete
              </p>
              <p className="text-sm font-semibold text-fg-dark mb-4">"{confirmDelete.name}"?</p>
              <p className="text-xs text-red-500 mb-6">
                This will also delete all {confirmDelete.test_case_count || 0} test cases and {confirmDelete.requirement_count || 0} requirements. This action cannot be undone.
              </p>
              <div className="flex justify-end gap-3">
                <button onClick={() => setConfirmDelete(null)} className="btn-secondary">Cancel</button>
                <button onClick={handleDelete} className="px-4 py-2 rounded-lg text-sm font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors">
                  Delete Project
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* New Project Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-fg-navy">New Project</h2>
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
                  <label className="label">Project Name</label>
                  <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g., Reltio Golden Record Testing"
                    className="input-field"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="label">Domain</label>
                  <DomainSelector value={newDomain} onChange={setNewDomain} />
                </div>

                {newDomain && (
                  <div className="animate-fade-in">
                    <label className="label">Sub-Domain</label>
                    <select
                      value={newSubDomain}
                      onChange={(e) => setNewSubDomain(e.target.value)}
                      className="input-field"
                    >
                      <option value="">Select sub-domain...</option>
                      {(SUB_DOMAINS[newDomain] || []).map((sd) => (
                        <option key={sd} value={sd}>{sd}</option>
                      ))}
                    </select>
                  </div>
                )}

                <div>
                  <label className="label">Description</label>
                  <textarea
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                    placeholder="Brief description of the QA scope..."
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
                    {creating ? 'Creating...' : 'Create Project'}
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

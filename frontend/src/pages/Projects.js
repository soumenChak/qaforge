import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { projectsAPI, usersAPI, agentKeyAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { DOMAIN_COLORS, DOMAIN_NAMES } from '../constants/domains';
import DomainSelector from '../components/DomainSelector';
import { PlusIcon, FunnelIcon, XMarkIcon, FolderIcon, EllipsisVerticalIcon, ArchiveBoxIcon, TrashIcon, ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/24/outline';

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

  const { isAdmin } = useAuth();
  const [wizardStep, setWizardStep] = useState(1);
  const [autoGenerateKey, setAutoGenerateKey] = useState(true);
  const [assignedUsers, setAssignedUsers] = useState([]);
  const [availableUsers, setAvailableUsers] = useState([]);
  const [generatedKey, setGeneratedKey] = useState(null);
  const [copied, setCopied] = useState(false);

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

  // Load available users when modal opens (admin only)
  useEffect(() => {
    if (showModal && isAdmin) {
      usersAPI.getAll().then(res => {
        setAvailableUsers((res.data || []).filter(u => u.is_active));
      }).catch(() => {});
    }
  }, [showModal, isAdmin]);

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
        auto_generate_key: autoGenerateKey,
        assigned_users: assignedUsers.length > 0 ? assignedUsers : undefined,
      });
      if (res.data.agent_api_key_plaintext) {
        setGeneratedKey(res.data.agent_api_key_plaintext);
        setWizardStep(3);
        loadProjects();
      } else {
        setShowModal(false);
        resetForm();
        navigate(`/projects/${res.data.id}`);
      }
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
    setWizardStep(1);
    setAutoGenerateKey(true);
    setAssignedUsers([]);
    setGeneratedKey(null);
    setCopied(false);
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
                <h2 className="text-lg font-bold text-fg-navy">
                  {wizardStep === 3 ? 'Project Created!' : 'New Project'}
                </h2>
                <button onClick={() => { setShowModal(false); resetForm(); }} className="text-fg-mid hover:text-fg-dark">
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              {/* Step indicators */}
              {wizardStep < 3 && (
                <div className="flex items-center gap-2 mb-6">
                  {[1, 2].map(step => (
                    <div key={step} className="flex items-center gap-2">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                        wizardStep >= step ? 'bg-fg-teal text-white' : 'bg-gray-200 text-gray-500'
                      }`}>{step}</div>
                      <span className="text-xs text-fg-mid">{step === 1 ? 'Details' : 'Team'}</span>
                      {step < 2 && <div className="w-8 h-px bg-gray-300" />}
                    </div>
                  ))}
                </div>
              )}

              {createError && (
                <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {createError}
                </div>
              )}

              {/* Step 1: Project Details */}
              {wizardStep === 1 && (
                <div className="space-y-5">
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
                      <select value={newSubDomain} onChange={(e) => setNewSubDomain(e.target.value)} className="input-field">
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
                  {isAdmin && (
                    <label className="flex items-center gap-2 text-sm text-fg-dark cursor-pointer">
                      <input
                        type="checkbox"
                        checked={autoGenerateKey}
                        onChange={(e) => setAutoGenerateKey(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-300 text-fg-teal focus:ring-fg-teal"
                      />
                      Auto-generate agent API key
                    </label>
                  )}
                  <div className="flex justify-end gap-3 pt-2">
                    <button type="button" onClick={() => { setShowModal(false); resetForm(); }} className="btn-secondary">Cancel</button>
                    {isAdmin ? (
                      <button
                        type="button"
                        onClick={() => {
                          if (!newName.trim() || !newDomain) { setCreateError('Name and domain are required.'); return; }
                          setCreateError('');
                          setWizardStep(2);
                        }}
                        className="btn-primary"
                      >Next: Assign Team</button>
                    ) : (
                      <button onClick={handleCreate} disabled={creating} className="btn-primary">
                        {creating ? 'Creating...' : 'Create Project'}
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Step 2: Assign Engineers */}
              {wizardStep === 2 && (
                <div className="space-y-5">
                  <div>
                    <label className="label">Assign Engineers (optional)</label>
                    <p className="text-xs text-fg-mid mb-3">Select team members who will work on this project.</p>
                    <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-3">
                      {availableUsers.filter(u => !u.roles?.includes('admin')).length === 0 ? (
                        <p className="text-sm text-fg-mid text-center py-4">No engineers available. Create users first.</p>
                      ) : (
                        availableUsers.filter(u => !u.roles?.includes('admin')).map(u => (
                          <label key={u.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={assignedUsers.includes(u.id)}
                              onChange={(e) => {
                                if (e.target.checked) setAssignedUsers([...assignedUsers, u.id]);
                                else setAssignedUsers(assignedUsers.filter(id => id !== u.id));
                              }}
                              className="w-4 h-4 rounded border-gray-300 text-fg-teal focus:ring-fg-teal"
                            />
                            <div>
                              <span className="text-sm font-medium text-fg-dark">{u.name}</span>
                              <span className="text-xs text-fg-mid ml-2">{u.email}</span>
                            </div>
                          </label>
                        ))
                      )}
                    </div>
                  </div>
                  <div className="flex justify-between pt-2">
                    <button type="button" onClick={() => setWizardStep(1)} className="btn-secondary">Back</button>
                    <button onClick={handleCreate} disabled={creating} className="btn-primary">
                      {creating ? 'Creating...' : 'Create Project'}
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Success + Agent Key */}
              {wizardStep === 3 && generatedKey && (
                <div className="space-y-5">
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                    <CheckIcon className="w-8 h-8 text-green-600 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-green-800">Project created with agent key!</p>
                  </div>
                  <div>
                    <label className="label">Add to your project's .env file:</label>
                    <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm text-green-400 relative">
                      <div>QAFORGE_API_URL=https://13.233.36.18:8080/api</div>
                      <div>QAFORGE_AGENT_KEY={generatedKey}</div>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(`QAFORGE_API_URL=https://13.233.36.18:8080/api\nQAFORGE_AGENT_KEY=${generatedKey}`);
                          setCopied(true);
                          setTimeout(() => setCopied(false), 3000);
                        }}
                        className="absolute top-2 right-2 p-1.5 rounded bg-gray-700 hover:bg-gray-600 transition-colors"
                        title="Copy to clipboard"
                      >
                        {copied ? (
                          <CheckIcon className="w-4 h-4 text-green-400" />
                        ) : (
                          <ClipboardDocumentIcon className="w-4 h-4 text-gray-400" />
                        )}
                      </button>
                    </div>
                  </div>
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <p className="text-xs font-semibold text-blue-800 mb-1">Or bootstrap via CLI:</p>
                    <code className="text-xs text-blue-700">
                      python scripts/qaforge.py setup --project "{newName}" --token "bootstrap-token"
                    </code>
                  </div>
                  <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                    <p className="text-xs font-semibold text-purple-800 mb-1">Using Claude Code MCP? Switch to this project:</p>
                    <p className="text-xs text-purple-700 mb-2">Tell Claude:</p>
                    <code className="block text-xs bg-white rounded px-3 py-2 border border-purple-200 font-mono text-purple-800 break-all">
                      connect to this project with key {generatedKey}
                    </code>
                  </div>
                  <p className="text-xs text-red-500">
                    This key is shown only once. Copy it now!
                  </p>
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={() => {
                        setShowModal(false);
                        resetForm();
                      }}
                      className="btn-primary"
                    >Done</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

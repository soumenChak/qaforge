import React, { useState, useEffect, useCallback } from 'react';
import { knowledgeAPI } from '../services/api';
import {
  BeakerIcon,
  PlusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  PencilSquareIcon,
  TrashIcon,
  CheckCircleIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

const DOMAIN_META = {
  mdm:       { label: 'MDM',              color: 'from-teal-500 to-emerald-600',   badge: 'bg-teal-100 text-teal-700' },
  ai:        { label: 'AI / GenAI',        color: 'from-purple-500 to-indigo-600',  badge: 'bg-purple-100 text-purple-700' },
  data_eng:  { label: 'Data Engineering',  color: 'from-blue-500 to-cyan-600',      badge: 'bg-blue-100 text-blue-700' },
  data_engineering: { label: 'Data Engineering', color: 'from-blue-500 to-cyan-600', badge: 'bg-blue-100 text-blue-700' },
  integration: { label: 'Integration',     color: 'from-orange-500 to-amber-600',   badge: 'bg-orange-100 text-orange-700' },
  digital:   { label: 'Digital',           color: 'from-pink-500 to-rose-600',      badge: 'bg-pink-100 text-pink-700' },
  app:       { label: 'Application',       color: 'from-gray-500 to-slate-600',     badge: 'bg-gray-100 text-gray-700' },
  general:   { label: 'General',           color: 'from-gray-400 to-gray-500',      badge: 'bg-gray-100 text-gray-600' },
};

export default function Frameworks() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [domainFilter, setDomainFilter] = useState('all');
  const [showAdd, setShowAdd] = useState(false);
  const [newEntry, setNewEntry] = useState({
    title: '', content: '', domain: 'mdm', sub_domain: '', tags: [], version: '1.0',
  });
  const [tagInput, setTagInput] = useState('');
  const [saving, setSaving] = useState(false);

  const loadFrameworks = useCallback(async () => {
    setLoading(true);
    try {
      const params = { entry_type: 'framework_pattern' };
      if (domainFilter !== 'all') params.domain = domainFilter;
      const resp = await knowledgeAPI.list(params);
      const data = resp.data;
      setEntries(data && data.items ? data.items : (Array.isArray(data) ? data : []));
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [domainFilter]);

  useEffect(() => { loadFrameworks(); }, [loadFrameworks]);

  const filtered = entries.filter((e) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      e.title?.toLowerCase().includes(q) ||
      e.content?.toLowerCase().includes(q) ||
      e.domain?.toLowerCase().includes(q) ||
      e.sub_domain?.toLowerCase().includes(q) ||
      (e.tags || []).some((t) => t.toLowerCase().includes(q))
    );
  });

  // Group by domain
  const grouped = {};
  filtered.forEach((e) => {
    const key = e.domain || 'general';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(e);
  });

  const handleAddTag = () => {
    const tag = tagInput.trim();
    if (tag && !newEntry.tags.includes(tag)) {
      setNewEntry({ ...newEntry, tags: [...newEntry.tags, tag] });
    }
    setTagInput('');
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newEntry.title.trim() || !newEntry.content.trim()) return;
    setSaving(true);
    try {
      await knowledgeAPI.create({
        ...newEntry,
        entry_type: 'framework_pattern',
      });
      setShowAdd(false);
      setNewEntry({ title: '', content: '', domain: 'mdm', sub_domain: '', tags: [] });
      loadFrameworks();
    } catch (err) {
      const d = err.response?.data?.detail;
      alert(typeof d === 'string' ? d : 'Failed to create framework entry.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id, title) => {
    if (!window.confirm(`Delete framework "${title}"?`)) return;
    try {
      await knowledgeAPI.delete(id);
      loadFrameworks();
    } catch {
      alert('Failed to delete.');
    }
  };

  const domains = [...new Set(entries.map((e) => e.domain || 'general'))].sort();

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-fg-navy flex items-center gap-2">
            <BeakerIcon className="w-7 h-7 text-fg-teal" />
            Testing Frameworks
          </h1>
          <p className="text-sm text-fg-mid mt-1">
            Reusable testing standards, architectural patterns, and quality gates by domain
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="btn-primary flex items-center gap-2 text-sm"
        >
          <PlusIcon className="w-4 h-4" />
          Add Framework
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="card-static p-3 text-center">
          <p className="text-2xl font-bold text-fg-navy">{entries.length}</p>
          <p className="text-xs text-fg-mid">Total Frameworks</p>
        </div>
        <div className="card-static p-3 text-center">
          <p className="text-2xl font-bold text-fg-navy">{domains.length}</p>
          <p className="text-xs text-fg-mid">Domains Covered</p>
        </div>
        <div className="card-static p-3 text-center">
          <p className="text-2xl font-bold text-fg-navy">
            {entries.reduce((sum, e) => sum + (e.usage_count || 0), 0)}
          </p>
          <p className="text-xs text-fg-mid">Times Used in Generation</p>
        </div>
        <div className="card-static p-3 text-center">
          <p className="text-2xl font-bold text-fg-navy">
            {entries.filter((e) => (e.usage_count || 0) > 0).length}
          </p>
          <p className="text-xs text-fg-mid">Active Frameworks</p>
        </div>
      </div>

      {/* Add Form */}
      {showAdd && (
        <div className="card-static p-5 mb-5 animate-slide-up">
          <h3 className="text-sm font-bold text-fg-navy mb-3 flex items-center gap-2">
            <SparklesIcon className="w-4 h-4 text-fg-teal" />
            New Testing Framework
          </h3>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <label className="label">Title</label>
              <input
                value={newEntry.title}
                onChange={(e) => setNewEntry({ ...newEntry, title: e.target.value })}
                placeholder="e.g., Reltio MDM Entity Testing Framework"
                className="input-field"
                autoFocus
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Content (guidelines, standards, checklist)</label>
              <textarea
                value={newEntry.content}
                onChange={(e) => setNewEntry({ ...newEntry, content: e.target.value })}
                placeholder="Describe the testing framework: what must be tested, quality gates, standards, patterns..."
                rows={6}
                className="input-field"
              />
            </div>
            <div>
              <label className="label">Domain</label>
              <select
                value={newEntry.domain}
                onChange={(e) => setNewEntry({ ...newEntry, domain: e.target.value })}
                className="input-field"
              >
                <option value="mdm">MDM</option>
                <option value="ai">AI / GenAI</option>
                <option value="data_eng">Data Engineering</option>
                <option value="integration">Integration</option>
                <option value="digital">Digital</option>
                <option value="general">General</option>
              </select>
            </div>
            <div>
              <label className="label">Sub-Domain</label>
              <input
                value={newEntry.sub_domain}
                onChange={(e) => setNewEntry({ ...newEntry, sub_domain: e.target.value })}
                placeholder="e.g., reltio, snowflake"
                className="input-field"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Version</label>
              <input
                value={newEntry.version}
                onChange={(e) => setNewEntry({ ...newEntry, version: e.target.value })}
                placeholder="e.g., 1.0"
                className="input-field w-32"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Tags</label>
              <div className="flex gap-2">
                <input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddTag(); } }}
                  placeholder="Add tag and press Enter"
                  className="input-field flex-1"
                />
                <button type="button" onClick={handleAddTag} className="btn-secondary text-sm">Add</button>
              </div>
              {newEntry.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {newEntry.tags.map((t) => (
                    <span key={t} className="badge badge-gray text-xs flex items-center gap-1">
                      {t}
                      <button type="button" onClick={() => setNewEntry({ ...newEntry, tags: newEntry.tags.filter((x) => x !== t) })}>
                        <XMarkIcon className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="sm:col-span-2 flex justify-end gap-3">
              <button type="button" onClick={() => setShowAdd(false)} className="btn-ghost text-sm">Cancel</button>
              <button type="submit" disabled={saving} className="btn-primary text-sm">
                {saving ? 'Saving...' : 'Create Framework'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Search + Domain Filter */}
      <div className="flex flex-wrap gap-3 mb-5">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-fg-mid" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search frameworks..."
            className="input-field pl-9"
          />
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setDomainFilter('all')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${domainFilter === 'all' ? 'bg-white text-fg-navy shadow-sm' : 'text-fg-mid hover:text-fg-dark'}`}
          >
            All
          </button>
          {domains.map((d) => (
            <button
              key={d}
              onClick={() => setDomainFilter(d)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${domainFilter === d ? 'bg-white text-fg-navy shadow-sm' : 'text-fg-mid hover:text-fg-dark'}`}
            >
              {(DOMAIN_META[d] || DOMAIN_META.general).label}
            </button>
          ))}
        </div>
      </div>

      {/* Frameworks grouped by domain */}
      {loading ? (
        <div className="text-center py-12 text-fg-mid">Loading frameworks...</div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="card-static p-12 text-center">
          <BeakerIcon className="w-12 h-12 mx-auto text-gray-300 mb-3" />
          <p className="text-fg-mid mb-2">No testing frameworks yet.</p>
          <p className="text-xs text-fg-mid">Add domain-specific testing standards, patterns, and quality gates.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([domain, items]) => {
            const meta = DOMAIN_META[domain] || DOMAIN_META.general;
            return (
              <div key={domain}>
                <div className="flex items-center gap-2 mb-3">
                  <div className={`w-1 h-6 rounded-full bg-gradient-to-b ${meta.color}`} />
                  <h2 className="text-sm font-bold text-fg-navy uppercase tracking-wide">
                    {meta.label}
                  </h2>
                  <span className="text-xs text-fg-mid">({items.length})</span>
                </div>
                <div className="space-y-2">
                  {items.map((entry) => {
                    const isExpanded = expandedId === entry.id;
                    return (
                      <div
                        key={entry.id}
                        className="card-static p-4 cursor-pointer hover:shadow-md transition-all duration-200"
                        onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-xxs px-2 py-0.5 rounded font-medium ${meta.badge}`}>
                                {meta.label}
                              </span>
                              {entry.version && (
                                <span className="text-xxs px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 font-mono font-bold">
                                  v{entry.version}
                                </span>
                              )}
                              {entry.sub_domain && (
                                <span className="badge badge-gray text-xs">{entry.sub_domain}</span>
                              )}
                              {(entry.usage_count || 0) > 0 && (
                                <span className="text-xxs text-fg-mid flex items-center gap-1">
                                  <CheckCircleIcon className="w-3 h-3 text-green-500" />
                                  Used {entry.usage_count}x
                                </span>
                              )}
                              {isExpanded
                                ? <ChevronUpIcon className="w-3.5 h-3.5 text-fg-mid" />
                                : <ChevronDownIcon className="w-3.5 h-3.5 text-fg-mid" />}
                            </div>
                            <p className="text-sm font-medium text-fg-dark">{entry.title}</p>
                            {!isExpanded && entry.content && (
                              <p className="text-xs text-fg-mid mt-1 line-clamp-2">{entry.content}</p>
                            )}
                            {isExpanded && (
                              <div className="mt-3">
                                <div className="bg-gray-50 rounded-lg p-4 text-xs text-fg-dark whitespace-pre-wrap leading-relaxed">
                                  {entry.content}
                                </div>
                                {(entry.tags || []).length > 0 && (
                                  <div className="flex flex-wrap gap-1 mt-3">
                                    {entry.tags.map((t) => (
                                      <span key={t} className="badge badge-gray text-xxs">{t}</span>
                                    ))}
                                  </div>
                                )}
                                <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-4 text-xs text-fg-mid">
                                  {entry.created_at && (
                                    <span>Created: {new Date(entry.created_at).toLocaleDateString()}</span>
                                  )}
                                  <span>Used {entry.usage_count || 0}x in test generation</span>
                                </div>
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-1 ml-3 flex-shrink-0">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDelete(entry.id, entry.title); }}
                              className="text-gray-300 hover:text-red-500 p-1 rounded hover:bg-red-50 transition-colors"
                              title="Delete"
                            >
                              <TrashIcon className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

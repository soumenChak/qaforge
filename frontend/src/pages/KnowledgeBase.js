import React, { useState, useEffect, useCallback } from 'react';
import { knowledgeAPI } from '../services/api';
import {
  MagnifyingGlassIcon,
  PlusIcon,
  XMarkIcon,
  BookOpenIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const DOMAIN_COLORS = {
  general: 'bg-gray-100 text-gray-700',
  mdm: 'bg-purple-100 text-purple-700',
  ai: 'bg-blue-100 text-blue-700',
  data_eng: 'bg-orange-100 text-orange-700',
};

const DOMAIN_NAMES = {
  general: 'General',
  mdm: 'MDM',
  ai: 'AI / GenAI',
  data_eng: 'Data Engineering',
};

const TYPE_COLORS = {
  pattern: 'bg-teal-100 text-teal-700',
  defect: 'bg-red-100 text-red-700',
  best_practice: 'bg-green-100 text-green-700',
  test_case: 'bg-blue-100 text-blue-700',
};

export default function KnowledgeBase() {
  const [query, setQuery] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [stats, setStats] = useState(null);
  const [showAdd, setShowAdd] = useState(false);

  // Add entry form
  const [newEntry, setNewEntry] = useState({
    title: '',
    content: '',
    domain: 'mdm',
    sub_domain: '',
    entry_type: 'pattern',
    tags: [],
  });
  const [tagInput, setTagInput] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState(null);

  // Browse state
  const [entries, setEntries] = useState([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [browseDomain, setBrowseDomain] = useState('');
  const [expandedId, setExpandedId] = useState(null);

  const loadStats = useCallback(async () => {
    try {
      const res = await knowledgeAPI.getStats();
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load KB stats:', err);
    }
  }, []);

  const loadEntries = useCallback(async (domain) => {
    setEntriesLoading(true);
    try {
      const params = { limit: 100 };
      if (domain) params.domain = domain;
      const res = await knowledgeAPI.list(params);
      setEntries(res.data || []);
    } catch (err) {
      console.error('Failed to load entries:', err);
    } finally {
      setEntriesLoading(false);
    }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadEntries(browseDomain); }, [loadEntries, browseDomain]);

  const handleSearch = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      const params = { q: query.trim() };
      if (domainFilter) params.domain = domainFilter;
      const res = await knowledgeAPI.search(params);
      setResults(res.data);
    } catch (err) {
      console.error('Search failed:', err);
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleAddEntry = async (e) => {
    e.preventDefault();
    if (!newEntry.title.trim() || !newEntry.content.trim()) {
      setAddError('Title and content are required.');
      return;
    }
    setAdding(true);
    setAddError('');
    try {
      await knowledgeAPI.create({
        ...newEntry,
        tags: newEntry.tags.length > 0 ? newEntry.tags : null,
      });
      setShowAdd(false);
      setNewEntry({ title: '', content: '', domain: 'mdm', sub_domain: '', entry_type: 'pattern', tags: [] });
      loadStats();
      loadEntries(browseDomain);
    } catch (err) {
      setAddError(err.response?.data?.detail || 'Failed to add entry.');
    } finally {
      setAdding(false);
    }
  };

  const addTag = () => {
    const tag = tagInput.trim();
    if (tag && !newEntry.tags.includes(tag)) {
      setNewEntry({ ...newEntry, tags: [...newEntry.tags, tag] });
    }
    setTagInput('');
  };

  const removeTag = (tag) => {
    setNewEntry({ ...newEntry, tags: newEntry.tags.filter((t) => t !== tag) });
  };

  const handleSeedKB = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const res = await knowledgeAPI.seed();
      setSeedResult(res.data);
      loadStats();
      loadEntries(browseDomain);
    } catch (err) {
      setSeedResult({ error: err.response?.data?.detail || 'Seeding failed.' });
    } finally {
      setSeeding(false);
    }
  };

  // Chart data from stats
  const chartData = stats?.entries_by_domain
    ? Object.entries(stats.entries_by_domain).map(([domain, count]) => ({ domain, count }))
    : [];

  return (
    <div className="page-container">
      <div className="section-header">
        <div>
          <h1 className="text-2xl font-bold text-fg-navy">Knowledge Base</h1>
          <p className="text-sm text-fg-mid mt-1">
            Domain-specific patterns, defects, and best practices
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
            <PlusIcon className="w-4 h-4" />
            Add Entry
          </button>
          <button
            onClick={handleSeedKB}
            disabled={seeding}
            className="btn-secondary flex items-center gap-2 border-teal-200 text-teal-700 hover:bg-teal-50"
          >
            <SparklesIcon className="w-4 h-4" />
            {seeding ? 'Seeding...' : 'Seed Reference Data'}
          </button>
        </div>
      </div>

      {/* Seed result banner */}
      {seedResult && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          seedResult.error
            ? 'bg-red-50 border border-red-200 text-red-700'
            : 'bg-green-50 border border-green-200 text-green-700'
        }`}>
          {seedResult.error
            ? seedResult.error
            : `Seeded ${seedResult.kb_created} KB entries and ${seedResult.templates_created} templates. Total: ${seedResult.total_entries} entries.`
          }
          {seedResult.kb_skipped > 0 && ` (${seedResult.kb_skipped} already existed)`}
        </div>
      )}

      {/* Empty state with seed prompt */}
      {stats && stats.total_entries === 0 && !searched && (
        <div className="card-static p-8 text-center mb-6 animate-fade-in">
          <BookOpenIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-fg-navy mb-2">Knowledge Base is Empty</h3>
          <p className="text-sm text-fg-mid mb-4 max-w-md mx-auto">
            Seed the knowledge base with reference patterns, best practices, and example test cases
            to improve AI test generation quality.
          </p>
          <button
            onClick={handleSeedKB}
            disabled={seeding}
            className="btn-primary flex items-center gap-2 mx-auto"
          >
            <SparklesIcon className="w-4 h-4" />
            {seeding ? 'Seeding...' : 'Seed Reference Data'}
          </button>
        </div>
      )}

      {/* Search */}
      <div className="card-static p-5 mb-6">
        <form onSubmit={handleSearch} className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[200px] relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-mid" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search knowledge base..."
              className="input-field pl-9"
            />
          </div>
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            className="input-field w-auto"
          >
            <option value="">All Domains</option>
            <option value="general">General</option>
            <option value="mdm">MDM</option>
            <option value="ai">AI / GenAI</option>
            <option value="data_eng">Data Engineering</option>
          </select>
          <button type="submit" disabled={searching || !query.trim()} className="btn-primary">
            {searching ? 'Searching...' : 'Search'}
          </button>
        </form>
      </div>

      {/* Search results */}
      {searched && (
        <div className="mb-8 animate-fade-in">
          <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">
            Search Results ({results.length})
          </h3>
          {results.length === 0 ? (
            <div className="card-static p-6 text-center text-fg-mid text-sm">
              No entries found matching your query.
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((entry) => (
                <div key={entry.id} className="card-static p-4">
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="text-sm font-bold text-fg-navy flex-1 mr-3">{entry.title}</h4>
                    <span className="text-xs text-fg-mid flex-shrink-0">
                      Used {entry.usage_count || 0}x
                    </span>
                  </div>
                  <div className="flex gap-2 mb-2">
                    <span className={`badge text-xs ${TYPE_COLORS[entry.entry_type] || 'badge-gray'}`}>
                      {entry.entry_type?.replace(/_/g, ' ')}
                    </span>
                    <span className={`badge text-xs ${DOMAIN_COLORS[entry.domain] || 'badge-gray'}`}>
                      {DOMAIN_NAMES[entry.domain] || entry.domain}
                    </span>
                    {entry.sub_domain && <span className="badge badge-gray text-xs">{entry.sub_domain}</span>}
                  </div>
                  <p className="text-xs text-fg-mid line-clamp-3">{entry.content}</p>
                  {entry.tags && entry.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {entry.tags.map((tag, i) => (
                        <span key={i} className="text-xxs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Browse Entries section */}
      {stats && stats.total_entries > 0 && (
        <div className="mb-8">
          {/* Domain filter tabs */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider">
              All Entries ({entries.length})
            </h3>
            <div className="flex gap-1">
              {[
                { key: '', label: 'All' },
                { key: 'general', label: 'General' },
                { key: 'mdm', label: 'MDM' },
                { key: 'ai', label: 'AI / GenAI' },
                { key: 'data_eng', label: 'Data Eng' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setBrowseDomain(tab.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    browseDomain === tab.key
                      ? 'bg-fg-teal text-white'
                      : 'bg-gray-100 text-fg-mid hover:bg-gray-200'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {entriesLoading ? (
            <div className="text-center py-8 text-fg-mid text-sm">Loading entries...</div>
          ) : entries.length === 0 ? (
            <div className="card-static p-6 text-center text-fg-mid text-sm">
              No entries found for this domain.
            </div>
          ) : (
            <div className="space-y-2">
              {entries.map((entry) => {
                const isExpanded = expandedId === entry.id;
                return (
                  <div
                    key={entry.id}
                    className="card-static overflow-hidden transition-all cursor-pointer hover:shadow-md"
                    onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  >
                    <div className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0 mr-3">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`badge text-xs ${TYPE_COLORS[entry.entry_type] || 'badge-gray'}`}>
                              {entry.entry_type?.replace(/_/g, ' ')}
                            </span>
                            <span className={`badge text-xs ${DOMAIN_COLORS[entry.domain] || 'badge-gray'}`}>
                              {DOMAIN_NAMES[entry.domain] || entry.domain}
                            </span>
                            {entry.usage_count > 0 && (
                              <span className="text-[10px] text-fg-mid">
                                Used {entry.usage_count}x in generation
                              </span>
                            )}
                          </div>
                          <h4 className="text-sm font-bold text-fg-navy">{entry.title}</h4>
                          {!isExpanded && (
                            <p className="text-xs text-fg-mid mt-1 line-clamp-1">{entry.content}</p>
                          )}
                        </div>
                        <span className="text-fg-mid text-xs flex-shrink-0 mt-1">
                          {isExpanded ? '▲' : '▼'}
                        </span>
                      </div>

                      {isExpanded && (
                        <div className="mt-3 animate-fade-in">
                          <p className="text-xs text-fg-dark whitespace-pre-line leading-relaxed bg-gray-50 rounded-lg p-3">
                            {entry.content}
                          </p>
                          {entry.tags && entry.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-3">
                              {entry.tags.map((tag, i) => (
                                <span key={i} className="text-xxs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Stats section */}
      {stats && stats.total_entries > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Stats summary */}
          <div className="card-static overflow-hidden">
            <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
            <div className="p-5">
              <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">
                Statistics
              </h3>
              <div className="text-3xl font-black text-fg-navy mb-4">
                {stats.total_entries || 0}
                <span className="text-sm font-normal text-fg-mid ml-2">total entries</span>
              </div>

              {stats.entries_by_type && Object.keys(stats.entries_by_type).length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-fg-mid uppercase">By Type</h4>
                  {Object.entries(stats.entries_by_type).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between">
                      <span className={`badge text-xs ${TYPE_COLORS[type] || 'badge-gray'}`}>
                        {type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-sm font-medium text-fg-dark">{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Chart */}
          <div className="card-static overflow-hidden">
            <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
            <div className="p-5">
              <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">
                Entries by Domain
              </h3>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="domain" tick={{ fontSize: 12, fill: '#50606c' }} />
                    <YAxis tick={{ fontSize: 12, fill: '#50606c' }} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: '8px',
                        border: '1px solid #e5e7eb',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                        fontSize: '12px',
                      }}
                    />
                    <Bar dataKey="count" fill="#2bb8c6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[220px]">
                  <p className="text-sm text-fg-mid">No data yet</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Entry modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-fg-navy">Add Knowledge Entry</h2>
                <button onClick={() => { setShowAdd(false); setAddError(''); }} className="text-fg-mid hover:text-fg-dark">
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              {addError && (
                <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {addError}
                </div>
              )}

              <form onSubmit={handleAddEntry} className="space-y-4">
                <div>
                  <label className="label">Title</label>
                  <input
                    value={newEntry.title}
                    onChange={(e) => setNewEntry({ ...newEntry, title: e.target.value })}
                    placeholder="e.g., Reltio merge survivorship pattern"
                    className="input-field"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="label">Content</label>
                  <textarea
                    value={newEntry.content}
                    onChange={(e) => setNewEntry({ ...newEntry, content: e.target.value })}
                    placeholder="Detailed description, test pattern, or best practice..."
                    rows={5}
                    className="input-field"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Domain</label>
                    <select
                      value={newEntry.domain}
                      onChange={(e) => setNewEntry({ ...newEntry, domain: e.target.value })}
                      className="input-field"
                    >
                      <option value="general">General</option>
                      <option value="mdm">MDM</option>
                      <option value="ai">AI / GenAI</option>
                      <option value="data_eng">Data Engineering</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">Entry Type</label>
                    <select
                      value={newEntry.entry_type}
                      onChange={(e) => setNewEntry({ ...newEntry, entry_type: e.target.value })}
                      className="input-field"
                    >
                      <option value="pattern">Pattern</option>
                      <option value="defect">Known Defect</option>
                      <option value="best_practice">Best Practice</option>
                      <option value="test_case">Test Case</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="label">Sub-Domain (optional)</label>
                  <input
                    value={newEntry.sub_domain}
                    onChange={(e) => setNewEntry({ ...newEntry, sub_domain: e.target.value })}
                    placeholder="e.g., Reltio, Databricks"
                    className="input-field"
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="label">Tags</label>
                  <div className="flex gap-2 mb-2">
                    <input
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                      placeholder="Add tag and press Enter..."
                      className="input-field flex-1"
                    />
                    <button type="button" onClick={addTag} className="btn-ghost text-sm">Add</button>
                  </div>
                  {newEntry.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {newEntry.tags.map((tag) => (
                        <span key={tag} className="badge badge-gray text-xs flex items-center gap-1">
                          {tag}
                          <button type="button" onClick={() => removeTag(tag)} className="hover:text-red-500">
                            <XMarkIcon className="w-3 h-3" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => { setShowAdd(false); setAddError(''); }} className="btn-secondary">
                    Cancel
                  </button>
                  <button type="submit" disabled={adding} className="btn-primary">
                    {adding ? 'Adding...' : 'Add Entry'}
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

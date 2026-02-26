import React, { useState, useMemo } from 'react';
import RatingWidget from './RatingWidget';

const PRIORITY_STYLES = {
  P1: 'bg-red-100 text-red-700',
  P2: 'bg-orange-100 text-orange-700',
  P3: 'bg-blue-100 text-blue-700',
  P4: 'bg-gray-100 text-gray-600',
};

const STATUS_STYLES = {
  draft: 'bg-gray-100 text-gray-600',
  active: 'bg-blue-100 text-blue-700',
  passed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  blocked: 'bg-yellow-100 text-yellow-700',
  deprecated: 'bg-gray-100 text-gray-500',
};

const EXEC_TYPE_STYLES = {
  api: { bg: 'bg-indigo-100 text-indigo-700', label: 'API', icon: '🌐' },
  ui: { bg: 'bg-purple-100 text-purple-700', label: 'UI', icon: '🖥️' },
  sql: { bg: 'bg-amber-100 text-amber-700', label: 'SQL', icon: '🗄️' },
  manual: { bg: 'bg-gray-100 text-gray-600', label: 'Manual', icon: '✋' },
};

/**
 * TestCaseTable -- Sortable, filterable test case data table.
 *
 * Props:
 *   testCases     - array of test case objects
 *   onRowClick    - callback(testCase) when a row is clicked
 *   onStatusChange - callback(testCase, newStatus) for inline status update
 *   selectedIds   - Set of selected test case IDs
 *   onSelectChange - callback(newSelectedIds) for checkbox selection
 *   loading       - boolean loading state
 *   pagination    - { page, pageSize, total, onPageChange, onPageSizeChange }
 */
export default function TestCaseTable({
  testCases = [],
  onRowClick,
  onStatusChange,
  selectedIds = new Set(),
  onSelectChange,
  loading = false,
  pagination,
}) {
  const [sortField, setSortField] = useState('test_case_id');
  const [sortDir, setSortDir] = useState('asc');

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const sorted = useMemo(() => {
    const copy = [...testCases];
    copy.sort((a, b) => {
      const aVal = a[sortField] || '';
      const bVal = b[sortField] || '';
      const cmp = typeof aVal === 'string' ? aVal.localeCompare(bVal) : aVal - bVal;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [testCases, sortField, sortDir]);

  const allSelected = testCases.length > 0 && testCases.every((tc) => selectedIds.has(tc.id));

  const toggleAll = () => {
    if (!onSelectChange) return;
    if (allSelected) {
      onSelectChange(new Set());
    } else {
      onSelectChange(new Set(testCases.map((tc) => tc.id)));
    }
  };

  const toggleOne = (id) => {
    if (!onSelectChange) return;
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectChange(next);
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="text-gray-300 ml-1">&uarr;&darr;</span>;
    return <span className="ml-1 text-fg-teal">{sortDir === 'asc' ? '\u2191' : '\u2193'}</span>;
  };

  const statuses = ['draft', 'active', 'passed', 'failed', 'blocked', 'deprecated'];

  if (loading) {
    return (
      <div className="card-static p-8">
        <div className="flex items-center justify-center gap-3 text-fg-mid">
          <svg className="animate-spin w-5 h-5 text-fg-teal" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading test cases...
        </div>
      </div>
    );
  }

  if (testCases.length === 0) {
    return (
      <div className="card-static p-10 text-center">
        <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25Z" />
        </svg>
        <p className="text-sm text-fg-mid">No test cases found.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="table-container bg-white">
        <table className="min-w-full divide-y divide-gray-100">
          <thead>
            <tr className="table-header">
              {onSelectChange && (
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="rounded border-gray-300 text-fg-teal focus:ring-fg-teal"
                  />
                </th>
              )}
              <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('test_case_id')}>
                TC ID <SortIcon field="test_case_id" />
              </th>
              <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('title')}>
                Title <SortIcon field="title" />
              </th>
              <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('priority')}>
                Priority <SortIcon field="priority" />
              </th>
              <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('execution_type')}>
                Type <SortIcon field="execution_type" />
              </th>
              <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('category')}>
                Category <SortIcon field="category" />
              </th>
              <th className="px-4 py-3 cursor-pointer select-none" onClick={() => handleSort('status')}>
                Status <SortIcon field="status" />
              </th>
              <th className="px-4 py-3">Rating</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {sorted.map((tc) => (
              <tr
                key={tc.id}
                className="table-row cursor-pointer"
                onClick={(e) => {
                  // Don't navigate when clicking checkbox or dropdown
                  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
                  onRowClick?.(tc);
                }}
              >
                {onSelectChange && (
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(tc.id)}
                      onChange={() => toggleOne(tc.id)}
                      className="rounded border-gray-300 text-fg-teal focus:ring-fg-teal"
                    />
                  </td>
                )}
                <td className="px-4 py-3 text-sm font-mono font-medium text-fg-tealDark whitespace-nowrap">
                  {tc.test_case_id}
                </td>
                <td className="px-4 py-3 text-sm text-fg-dark max-w-xs truncate">
                  {tc.title}
                </td>
                <td className="px-4 py-3">
                  <span className={`badge ${PRIORITY_STYLES[tc.priority] || PRIORITY_STYLES.P3}`}>
                    {tc.priority}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {(() => {
                    const et = EXEC_TYPE_STYLES[tc.execution_type] || EXEC_TYPE_STYLES.api;
                    return (
                      <span className={`badge text-xs ${et.bg}`}>
                        {et.icon} {et.label}
                      </span>
                    );
                  })()}
                </td>
                <td className="px-4 py-3 text-sm text-fg-mid capitalize">
                  {tc.category?.replace(/_/g, ' ')}
                </td>
                <td className="px-4 py-3">
                  {onStatusChange ? (
                    <select
                      value={tc.status}
                      onChange={(e) => onStatusChange(tc, e.target.value)}
                      className="input-field text-xs py-1 w-auto"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {statuses.map((s) => (
                        <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                      ))}
                    </select>
                  ) : (
                    <span className={`badge ${STATUS_STYLES[tc.status] || STATUS_STYLES.draft}`}>
                      {tc.status}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <RatingWidget value={tc.rating || 0} readOnly size="sm" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {pagination && (
        <div className="flex items-center justify-between mt-4 px-1">
          <div className="flex items-center gap-2 text-sm text-fg-mid">
            <span>Show</span>
            <select
              value={pagination.pageSize}
              onChange={(e) => pagination.onPageSizeChange(Number(e.target.value))}
              className="input-field text-sm py-1 w-auto"
            >
              {[10, 25, 50].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            <span>per page</span>
            <span className="ml-4">
              {pagination.total} total
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              disabled={pagination.page <= 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
              className="btn-ghost text-sm disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-sm font-medium text-fg-dark px-2">
              Page {pagination.page}
            </span>
            <button
              disabled={pagination.page * pagination.pageSize >= pagination.total}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
              className="btn-ghost text-sm disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

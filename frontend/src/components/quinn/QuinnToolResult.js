import React, { useState } from 'react';
import {
  ChartBarIcon,
  DocumentTextIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

function StatMini({ label, value, color = 'text-fg-navy' }) {
  return (
    <div className="text-center">
      <div className={`text-lg font-bold ${color}`}>{value ?? '-'}</div>
      <div className="text-xxs text-gray-500">{label}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    passed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    draft: 'bg-gray-100 text-gray-600',
    approved: 'bg-blue-100 text-blue-700',
    executed: 'bg-purple-100 text-purple-700',
    active: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  };
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-xxs font-medium ${colors[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  );
}


export default function QuinnToolResult({ toolName, result }) {
  const [expanded, setExpanded] = useState(false);

  if (result?.error) {
    return (
      <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
        Tool error: {result.error}
      </div>
    );
  }

  // Project summary
  if (toolName === 'get_project_summary') {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-fg-navy">
          <ChartBarIcon className="w-4 h-4 text-fg-teal" />
          Project Summary
        </div>
        <div className="grid grid-cols-4 gap-2">
          <StatMini label="Requirements" value={result.requirements} />
          <StatMini label="Test Cases" value={result.test_cases} />
          <StatMini label="Plans" value={result.test_plans} />
          <StatMini label="Pass Rate" value={result.pass_rate ? `${result.pass_rate}%` : '-'} color={result.pass_rate >= 80 ? 'text-green-600' : 'text-amber-600'} />
        </div>
        {result.tc_by_status && Object.keys(result.tc_by_status).length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {Object.entries(result.tc_by_status).map(([s, c]) => (
              <span key={s} className="text-xxs px-1.5 py-0.5 rounded bg-white border border-gray-200">
                {s}: <strong>{c}</strong>
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Test case list
  if (toolName === 'list_test_cases' && result.test_cases) {
    const cases = result.test_cases;
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg-navy">
            <ClipboardDocumentListIcon className="w-4 h-4 text-fg-teal" />
            Test Cases ({result.total})
          </div>
        </div>
        <div className="space-y-1">
          {cases.slice(0, expanded ? cases.length : 5).map((tc, i) => (
            <div key={i} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
              <code className="text-fg-tealDark font-mono font-medium">{tc.test_case_id}</code>
              <span className="flex-1 truncate">{tc.title}</span>
              <StatusBadge status={tc.status} />
              <span className="text-xxs text-gray-400">{tc.priority}</span>
            </div>
          ))}
        </div>
        {cases.length > 5 && (
          <button onClick={() => setExpanded(!expanded)} className="text-xs text-fg-teal hover:text-fg-tealDark font-medium">
            {expanded ? 'Show less' : `Show all ${cases.length}`}
          </button>
        )}
      </div>
    );
  }

  // Test plans
  if (toolName === 'list_test_plans' && result.test_plans) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-fg-navy">
          <DocumentTextIcon className="w-4 h-4 text-fg-teal" />
          Test Plans ({result.total})
        </div>
        {result.test_plans.map((p, i) => (
          <div key={i} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
            <span className="flex-1 font-medium">{p.name}</span>
            <StatusBadge status={p.status} />
            <span className="text-xxs text-gray-400">{p.test_case_count} TCs</span>
          </div>
        ))}
      </div>
    );
  }

  // Execution results
  if (toolName === 'get_execution_results' && result.results) {
    const passed = result.results.filter((r) => r.status === 'passed').length;
    const failed = result.results.filter((r) => r.status === 'failed').length;
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-fg-navy">
          Execution Results
        </div>
        <div className="flex gap-3 text-xs">
          <span className="flex items-center gap-1 text-green-600">
            <CheckCircleIcon className="w-3.5 h-3.5" /> {passed} passed
          </span>
          <span className="flex items-center gap-1 text-red-600">
            <XCircleIcon className="w-3.5 h-3.5" /> {failed} failed
          </span>
        </div>
        {result.total > 0 && (
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-green-500 h-2 rounded-full transition-all"
              style={{ width: `${(passed / result.total) * 100}%` }}
            />
          </div>
        )}
      </div>
    );
  }

  // Requirements
  if (toolName === 'list_requirements' && result.requirements) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-fg-navy">
          <DocumentTextIcon className="w-4 h-4 text-fg-teal" />
          Requirements ({result.total})
        </div>
        {result.requirements.slice(0, 8).map((r, i) => (
          <div key={i} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
            <code className="text-fg-tealDark font-mono font-medium">{r.req_id}</code>
            <span className="flex-1 truncate">{r.title}</span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </div>
    );
  }

  // KB stats
  if (toolName === 'get_kb_stats') {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="text-xs font-semibold text-fg-navy">Knowledge Base Stats</div>
        <div className="text-sm">
          <strong>{result.total_entries}</strong> entries for <strong>{result.domain}</strong>
        </div>
        {result.by_type && (
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(result.by_type).map(([type, count]) => (
              <span key={type} className="text-xxs px-1.5 py-0.5 rounded bg-white border border-gray-200">
                {type}: <strong>{count}</strong>
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Search results
  if (toolName === 'search_knowledge_base' && result.results) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="text-xs font-semibold text-fg-navy">KB Search: "{result.query}"</div>
        {result.results.length === 0 ? (
          <p className="text-xs text-gray-500">No results found.</p>
        ) : (
          result.results.slice(0, 5).map((e, i) => (
            <div key={i} className="text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
              <div className="font-medium">{e.title}</div>
              <div className="text-gray-500 mt-0.5 line-clamp-2">{e.content}</div>
            </div>
          ))
        )}
      </div>
    );
  }

  // Single test case detail
  if (toolName === 'get_test_case' && result.test_case_id) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="flex items-center gap-2">
          <code className="text-fg-tealDark font-mono font-bold text-sm">{result.test_case_id}</code>
          <StatusBadge status={result.status} />
          <span className="text-xxs text-gray-400">{result.priority}</span>
        </div>
        <div className="text-sm font-medium">{result.title}</div>
        {result.description && <p className="text-xs text-gray-600">{result.description}</p>}
        {result.test_steps && (
          <div className="space-y-1 mt-1">
            {result.test_steps.slice(0, expanded ? undefined : 3).map((step, i) => (
              <div key={i} className="text-xs bg-white rounded px-2 py-1 border border-gray-100">
                <span className="font-medium text-fg-teal">Step {step.step_number}:</span>{' '}
                {step.action}
              </div>
            ))}
            {result.test_steps.length > 3 && (
              <button onClick={() => setExpanded(!expanded)} className="text-xs text-fg-teal hover:text-fg-tealDark font-medium">
                {expanded ? 'Show less' : `Show all ${result.test_steps.length} steps`}
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  // Test plan summary
  if (toolName === 'get_test_plan_summary' && result.name) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-fg-navy">
          {result.name} <StatusBadge status={result.status} />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <StatMini label="Test Cases" value={result.test_case_count} />
          <StatMini label="Passed" value={result.passed} color="text-green-600" />
          <StatMini label="Pass Rate" value={result.pass_rate ? `${result.pass_rate}%` : '-'} />
        </div>
      </div>
    );
  }

  // Generic fallback
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
      <div className="text-xxs text-gray-500 mb-1">Tool: {toolName}</div>
      <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto max-h-40">
        {JSON.stringify(result, null, 2)}
      </pre>
    </div>
  );
}

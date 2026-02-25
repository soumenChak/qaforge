import React from 'react';

const DOMAINS = [
  {
    key: 'mdm',
    name: 'MDM',
    description: 'Master Data Management - Reltio, Semarchy, data quality',
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
      </svg>
    ),
  },
  {
    key: 'ai',
    name: 'AI / GenAI',
    description: 'AI pipelines, LLM integration, RAG, ML models',
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
      </svg>
    ),
  },
  {
    key: 'data_eng',
    name: 'Data Engineering',
    description: 'ETL/ELT pipelines, Databricks, Snowflake, streaming',
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
      </svg>
    ),
  },
];

/**
 * DomainSelector -- 3-card domain picker.
 *
 * Props:
 *   value    - currently selected domain key
 *   onChange - callback(domainKey)
 *   className - extra classes
 */
export default function DomainSelector({ value, onChange, className = '' }) {
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-3 gap-3 ${className}`}>
      {DOMAINS.map((domain) => {
        const selected = value === domain.key;
        return (
          <button
            key={domain.key}
            type="button"
            onClick={() => onChange(domain.key)}
            className={`p-4 rounded-xl border-2 text-left transition-all duration-150
              ${selected
                ? 'border-fg-teal bg-fg-tealLight shadow-md'
                : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
              }`}
          >
            <div className={`mb-2 ${selected ? 'text-fg-teal' : 'text-fg-mid'}`}>
              {domain.icon}
            </div>
            <p className={`font-bold text-sm ${selected ? 'text-fg-tealDark' : 'text-fg-navy'}`}>
              {domain.name}
            </p>
            <p className="text-xs text-fg-mid mt-1 line-clamp-2">
              {domain.description}
            </p>
          </button>
        );
      })}
    </div>
  );
}

export { DOMAINS };

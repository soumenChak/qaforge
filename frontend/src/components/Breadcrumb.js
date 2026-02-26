import React from 'react';
import { Link } from 'react-router-dom';

/**
 * Breadcrumb -- Lightweight navigation breadcrumb.
 *
 * Props:
 *   items - Array of { label, to? }
 *           The last item is the current page (rendered as plain dark text, no link).
 *           All other items are rendered as gray links with ">" separators.
 *
 * Example:
 *   <Breadcrumb items={[
 *     { label: 'Projects', to: '/projects' },
 *     { label: project.name, to: `/projects/${project.id}` },
 *     { label: 'TC-001' },
 *   ]} />
 */
export default function Breadcrumb({ items = [] }) {
  if (items.length === 0) return null;

  return (
    <nav className="flex items-center gap-1.5 text-xs mb-4" aria-label="Breadcrumb">
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        return (
          <React.Fragment key={idx}>
            {idx > 0 && (
              <span className="text-gray-400 select-none">&gt;</span>
            )}
            {isLast || !item.to ? (
              <span className="font-medium text-fg-dark truncate max-w-[200px]">{item.label}</span>
            ) : (
              <Link
                to={item.to}
                className="text-fg-mid hover:text-fg-teal transition-colors truncate max-w-[200px]"
              >
                {item.label}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

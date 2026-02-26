import React from 'react';

/**
 * Shared loading spinner — replaces the SVG spinner duplicated across 9+ pages.
 *
 * Props:
 *   size  - 'sm' (w-4 h-4), 'md' (w-8 h-8, default), 'lg' (w-12 h-12)
 *   className - extra classes for the wrapper div
 *   inline - if true, renders without centering wrapper (for inline use)
 */
export default function Spinner({ size = 'md', className = '', inline = false }) {
  const sizeMap = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' };
  const sizeClass = sizeMap[size] || sizeMap.md;

  const svg = (
    <svg className={`animate-spin ${sizeClass} text-fg-teal`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );

  if (inline) return svg;

  return (
    <div className={`flex items-center justify-center py-20 ${className}`}>
      {svg}
    </div>
  );
}

import React from 'react';

/**
 * StatCard -- Orbit-style stat card with optional gradient accent bar.
 *
 * Props:
 *   label      - uppercase small label text
 *   value      - large display value (string or number)
 *   icon       - optional HeroIcon component
 *   trend      - optional { value: number, label: string } trend indicator
 *   accentFrom - tailwind gradient from color (default: 'from-fg-teal')
 *   accentTo   - tailwind gradient to color (default: 'to-fg-green')
 *   className  - extra container classes
 */
export default function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  accentFrom = 'from-fg-teal',
  accentTo = 'to-fg-green',
  className = '',
}) {
  return (
    <div className={`card-static overflow-hidden ${className}`}>
      {/* Gradient accent bar */}
      <div className={`h-1 bg-gradient-to-r ${accentFrom} ${accentTo}`} />

      <div className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-fg-mid mb-1">
              {label}
            </p>
            <p className="text-3xl font-black text-fg-navy leading-tight truncate">
              {value}
            </p>
          </div>

          {Icon && (
            <div className="flex-shrink-0 ml-3 w-10 h-10 rounded-lg bg-fg-tealLight flex items-center justify-center">
              <Icon className="w-5 h-5 text-fg-teal" />
            </div>
          )}
        </div>

        {trend && (
          <div className="mt-3 flex items-center gap-1.5">
            {trend.value > 0 ? (
              <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
              </svg>
            ) : trend.value < 0 ? (
              <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6 9 12.75l4.286-4.286a11.948 11.948 0 0 1 4.306 6.43l.776 2.898m0 0 3.182-5.511m-3.182 5.51-5.511-3.181" />
              </svg>
            ) : null}
            <span className={`text-xs font-medium ${
              trend.value > 0 ? 'text-green-600' : trend.value < 0 ? 'text-red-600' : 'text-fg-mid'
            }`}>
              {trend.value > 0 ? '+' : ''}{trend.value}
            </span>
            {trend.label && (
              <span className="text-xs text-fg-mid">{trend.label}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

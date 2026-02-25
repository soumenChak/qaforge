import React, { useState } from 'react';

/**
 * RatingWidget -- Star rating component with optional feedback textarea.
 *
 * Props:
 *   value        - current rating (0-5)
 *   onChange     - callback(rating) when stars are clicked
 *   onSubmit     - callback({ rating, feedback }) for submission
 *   readOnly     - if true, stars are display-only
 *   size         - 'sm' | 'md' | 'lg' (default: 'md')
 *   showFeedback - show textarea when rating is selected (default: true when onSubmit is present)
 *   className    - extra classes
 */
export default function RatingWidget({
  value = 0,
  onChange,
  onSubmit,
  readOnly = false,
  size = 'md',
  showFeedback,
  className = '',
}) {
  const [hovered, setHovered] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localValue, setLocalValue] = useState(value);

  const displayValue = readOnly ? value : localValue;
  const shouldShowFeedback = showFeedback !== undefined ? showFeedback : !!onSubmit;

  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-7 h-7',
  };

  const starSize = sizeClasses[size] || sizeClasses.md;

  const handleClick = (star) => {
    if (readOnly) return;
    setLocalValue(star);
    if (onChange) onChange(star);
  };

  const handleSubmit = async () => {
    if (!onSubmit || localValue === 0) return;
    setSubmitting(true);
    try {
      await onSubmit({ rating: localValue, feedback_text: feedback || null });
      setFeedback('');
    } catch (err) {
      // Error handled by parent
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={className}>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => {
          const filled = star <= (hovered || displayValue);
          return (
            <button
              key={star}
              type="button"
              disabled={readOnly}
              className={`transition-colors duration-100 ${
                readOnly ? 'cursor-default' : 'cursor-pointer hover:scale-110'
              } transform`}
              onMouseEnter={() => !readOnly && setHovered(star)}
              onMouseLeave={() => !readOnly && setHovered(0)}
              onClick={() => handleClick(star)}
              aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
            >
              <svg
                className={`${starSize} ${
                  filled ? 'text-fg-teal' : 'text-gray-300'
                }`}
                fill={filled ? 'currentColor' : 'none'}
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
                />
              </svg>
            </button>
          );
        })}

        {displayValue > 0 && (
          <span className="ml-2 text-sm font-medium text-fg-mid">
            {displayValue}/5
          </span>
        )}
      </div>

      {/* Feedback section appears when stars are selected */}
      {shouldShowFeedback && localValue > 0 && !readOnly && (
        <div className="mt-3 animate-fade-in">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Optional feedback about this test case..."
            rows={3}
            className="input-field"
          />
          <div className="mt-2 flex justify-end">
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="btn-primary text-sm"
            >
              {submitting ? 'Submitting...' : 'Submit Rating'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

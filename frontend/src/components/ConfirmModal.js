import React, { useEffect, useCallback } from 'react';

/**
 * ConfirmModal -- Shared styled confirmation dialog to replace window.confirm().
 *
 * Props:
 *   isOpen        - Boolean, controls visibility
 *   onClose       - Called when Cancel / backdrop / Escape pressed
 *   onConfirm     - Called when Confirm button clicked
 *   title         - Bold heading text  (default: "Are you sure?")
 *   message       - Gray body text     (default: "")
 *   confirmText   - Confirm button label (default: "Confirm")
 *   confirmColor  - 'red' for destructive actions, 'teal' for normal (default: 'teal')
 */
export default function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title = 'Are you sure?',
  message = '',
  confirmText = 'Confirm',
  confirmColor = 'teal',
}) {
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  const confirmBtnClass =
    confirmColor === 'red'
      ? 'bg-red-600 text-white hover:bg-red-700'
      : 'bg-fg-teal text-white hover:bg-fg-tealDark';

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-xl max-w-sm w-full animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          <h2 className="text-lg font-bold text-fg-navy mb-2">{title}</h2>
          {message && (
            <p className="text-sm text-fg-mid mb-6">{message}</p>
          )}
          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${confirmBtnClass}`}
            >
              {confirmText}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

import React, { useState, useRef, useEffect } from 'react';
import { PaperAirplaneIcon, StopIcon } from '@heroicons/react/24/solid';

export default function QuinnInput({ onSend, isStreaming, onStop }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [text]);

  const handleSend = () => {
    if (!text.trim() || isStreaming) return;
    onSend(text.trim());
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white p-3">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Quinn anything..."
          rows={1}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm
            focus:outline-none focus:border-fg-teal focus:ring-1 focus:ring-fg-teal
            placeholder-gray-400 scrollbar-thin"
          disabled={isStreaming}
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="flex-shrink-0 w-9 h-9 rounded-lg bg-red-500 text-white
              flex items-center justify-center hover:bg-red-600 transition-colors"
            title="Stop"
          >
            <StopIcon className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!text.trim()}
            className="flex-shrink-0 w-9 h-9 rounded-lg bg-fg-teal text-white
              flex items-center justify-center hover:bg-fg-tealDark transition-colors
              disabled:opacity-40 disabled:cursor-not-allowed"
            title="Send"
          >
            <PaperAirplaneIcon className="w-4 h-4" />
          </button>
        )}
      </div>
      <p className="text-xxs text-gray-400 mt-1.5 px-1">
        Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}

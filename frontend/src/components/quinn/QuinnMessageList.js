import React, { useRef, useEffect } from 'react';
import QuinnMessage from './QuinnMessage';

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-3 animate-fade-in">
      <div className="bg-white border border-gray-100 shadow-sm rounded-xl rounded-bl-sm px-4 py-3">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 bg-fg-teal rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-2 h-2 bg-fg-teal rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-2 h-2 bg-fg-teal rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  );
}

function StreamingMessage({ text }) {
  if (!text) return null;
  return (
    <div className="flex justify-start mb-3">
      <div className="max-w-[85%] px-3.5 py-2.5 rounded-xl rounded-bl-sm bg-white border border-gray-100 shadow-sm text-sm leading-relaxed text-fg-dark">
        <p className="whitespace-pre-wrap">{text}<span className="inline-block w-1.5 h-4 bg-fg-teal animate-pulse ml-0.5 align-middle rounded-sm" /></p>
      </div>
    </div>
  );
}

function ToolActivity({ activity }) {
  if (!activity) return null;
  return (
    <div className="flex justify-start mb-2 animate-fade-in">
      <div className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs flex items-center gap-1.5 text-amber-700">
        <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40" strokeDashoffset="10" />
        </svg>
        <span>Using <code className="font-mono">{activity.tool}</code>...</span>
      </div>
    </div>
  );
}


export default function QuinnMessageList({ messages, streamingText, isStreaming, toolActivity }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, toolActivity]);

  const isEmpty = messages.length === 0 && !streamingText && !isStreaming;

  if (isEmpty) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-6 text-center">
        <div className="w-12 h-12 rounded-full bg-gradient-to-r from-fg-teal to-fg-green flex items-center justify-center mb-4">
          <span className="text-white text-lg font-bold">Q</span>
        </div>
        <h3 className="text-base font-bold text-fg-navy mb-2">Hi! I'm Quinn</h3>
        <p className="text-sm text-gray-500 max-w-xs">
          Your QA assistant. Ask me about test cases, coverage, execution results, or anything about this project.
        </p>
        <div className="mt-6 space-y-2 w-full max-w-xs">
          {[
            'What is the current pass rate?',
            'Show me the test cases',
            'What needs review?',
          ].map((suggestion) => (
            <div
              key={suggestion}
              className="text-xs text-fg-teal bg-fg-tealLight rounded-lg px-3 py-2 cursor-default text-center"
            >
              {suggestion}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 scrollbar-thin">
      {messages.map((msg) => (
        <QuinnMessage key={msg.id} message={msg} />
      ))}
      {toolActivity && <ToolActivity activity={toolActivity} />}
      {isStreaming && !streamingText && !toolActivity && <TypingIndicator />}
      {streamingText && <StreamingMessage text={streamingText} />}
      <div ref={bottomRef} />
    </div>
  );
}

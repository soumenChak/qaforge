import React, { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import {
  XMarkIcon,
  ClockIcon,
  Bars3BottomLeftIcon,
} from '@heroicons/react/24/outline';
import useQuinnChat from '../../hooks/useQuinnChat';
import QuinnMessageList from './QuinnMessageList';
import QuinnInput from './QuinnInput';
import QuinnSessionList from './QuinnSessionList';

export default function QuinnPanel({ isOpen, onClose }) {
  const location = useLocation();
  const [showHistory, setShowHistory] = useState(false);

  // Extract project ID from URL: /projects/:id/*
  const projectId = React.useMemo(() => {
    const match = location.pathname.match(/\/projects\/([^/]+)/);
    return match ? match[1] : null;
  }, [location.pathname]);

  const {
    sessions,
    activeSessionId,
    messages,
    streamingText,
    isStreaming,
    toolActivity,
    error,
    createSession,
    loadSession,
    deleteSession,
    sendMessage,
    stopStreaming,
  } = useQuinnChat(projectId);

  // Keyboard shortcut: Escape to close
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  // Cmd+K to toggle
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleSend = useCallback((content) => {
    setShowHistory(false);
    sendMessage(content);
  }, [sendMessage]);

  const handleNewChat = useCallback(() => {
    createSession();
    setShowHistory(false);
  }, [createSession]);

  const handleSelectSession = useCallback((sessionId) => {
    loadSession(sessionId);
    setShowHistory(false);
  }, [loadSession]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop for mobile */}
      <div
        className="fixed inset-0 bg-black/30 z-40 lg:hidden"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="fixed top-0 right-0 h-full z-50 flex flex-col
          w-full sm:w-[420px]
          bg-white border-l border-gray-200 shadow-xl
          animate-slide-in-right"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-fg-navy to-fg-dark flex-shrink-0">
          <div className="w-8 h-8 rounded-full bg-gradient-to-r from-fg-teal to-fg-green flex items-center justify-center flex-shrink-0">
            <span className="text-white text-sm font-bold">Q</span>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-white font-bold text-sm">Quinn</h3>
            <p className="text-gray-400 text-xxs truncate">
              {projectId ? 'QA Assistant' : 'Select a project first'}
            </p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              title="Chat history"
            >
              {showHistory ? (
                <Bars3BottomLeftIcon className="w-4 h-4" />
              ) : (
                <ClockIcon className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              title="Close (Esc)"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* No project selected */}
        {!projectId ? (
          <div className="flex-1 flex items-center justify-center px-6 text-center">
            <div>
              <p className="text-sm text-gray-500 mb-2">
                Navigate to a project to start chatting with Quinn.
              </p>
              <p className="text-xs text-gray-400">
                Quinn needs project context to assist you.
              </p>
            </div>
          </div>
        ) : showHistory ? (
          <QuinnSessionList
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={handleSelectSession}
            onDelete={deleteSession}
            onNew={handleNewChat}
            onClose={() => setShowHistory(false)}
          />
        ) : (
          <>
            {/* Error banner */}
            {error && (
              <div className="mx-3 mt-2 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 animate-fade-in">
                {error}
              </div>
            )}

            {/* Messages */}
            <QuinnMessageList
              messages={messages}
              streamingText={streamingText}
              isStreaming={isStreaming}
              toolActivity={toolActivity}
            />

            {/* Input */}
            <QuinnInput
              onSend={handleSend}
              isStreaming={isStreaming}
              onStop={stopStreaming}
            />
          </>
        )}
      </div>
    </>
  );
}

import React, { useState, useRef, useEffect } from 'react';
import { testCasesAPI } from '../services/api';
import {
  PaperAirplaneIcon,
  SparklesIcon,
  XMarkIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline';

/**
 * Chat-based test generation component (Feature 6).
 *
 * Multi-turn conversational UI where an AI agent asks clarifying questions
 * before generating test cases. Falls back to quick generation if the user
 * prefers to skip the conversation.
 */
export default function ChatGenerator({ projectId, onGenerated, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedTcs, setGeneratedTcs] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const res = await testCasesAPI.chatGenerate(projectId, {
        messages: newMessages,
      });

      const data = res.data;
      const assistantMsg = data.message;

      setMessages(prev => [...prev, assistantMsg]);

      if (data.action === 'generate' && data.test_cases) {
        setGeneratedTcs(data.test_cases);
        if (onGenerated) {
          onGenerated(data.test_cases);
        }
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.response?.data?.detail || err.message}. Please try again.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl h-[600px] flex flex-col animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ChatBubbleLeftRightIcon className="w-5 h-5 text-fg-teal" />
            <h3 className="text-sm font-semibold text-fg-dark">Test Generation Agent</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full hover:bg-gray-100 transition-colors"
          >
            <XMarkIcon className="w-5 h-5 text-fg-mid" />
          </button>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-8">
              <SparklesIcon className="w-10 h-10 text-fg-teal/30 mx-auto mb-3" />
              <p className="text-sm text-fg-mid">
                Tell me what you want to test. I'll review your project context and ask
                clarifying questions if needed before generating test cases.
              </p>
              <div className="mt-4 space-y-2">
                {[
                  'Generate API smoke tests for all endpoints',
                  'Create CRUD lifecycle tests for candidates',
                  'Test the login flow and role-based access',
                ].map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(suggestion)}
                    className="block mx-auto text-xs px-3 py-1.5 rounded-full bg-gray-100 text-fg-dark hover:bg-gray-200 transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-fg-teal text-white rounded-br-md'
                    : 'bg-gray-100 text-fg-dark rounded-bl-md'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          {/* Generation complete notice */}
          {generatedTcs && (
            <div className="p-4 rounded-lg bg-green-50 border border-green-200">
              <p className="text-sm font-semibold text-green-800 mb-1">
                ✓ Generated {generatedTcs.length} test case(s)
              </p>
              <p className="text-xs text-green-700">
                Test cases have been saved to your project. You can view them in the Test Cases tab.
              </p>
              <button
                onClick={onClose}
                className="mt-2 text-xs px-3 py-1.5 rounded bg-green-600 text-white hover:bg-green-700 font-medium transition-colors"
              >
                View Test Cases
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="px-5 py-3 border-t border-gray-200">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={messages.length === 0 ? "Describe what you want to test..." : "Reply to the agent..."}
              rows={1}
              className="flex-1 resize-none input py-2.5 text-sm max-h-24"
              disabled={loading || !!generatedTcs}
              style={{ minHeight: '42px' }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading || !!generatedTcs}
              className="btn btn-primary p-2.5 rounded-xl"
            >
              <PaperAirplaneIcon className="w-4 h-4" />
            </button>
          </div>
          {!generatedTcs && (
            <p className="text-[10px] text-fg-mid mt-1.5">
              Press Enter to send · Shift+Enter for new line
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

import { useState, useCallback, useRef, useEffect } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

function getAuthHeaders() {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function useQuinnChat(projectId) {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [toolActivity, setToolActivity] = useState(null); // {tool, status}
  const [error, setError] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const abortRef = useRef(null);

  // Fetch sessions for the project
  const fetchSessions = useCallback(async () => {
    if (!projectId) return;
    setLoadingSessions(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/chat/sessions`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error('Failed to fetch sessions');
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      console.error('Failed to fetch sessions:', e);
    } finally {
      setLoadingSessions(false);
    }
  }, [projectId]);

  // Create a new session
  const createSession = useCallback(async (title = null) => {
    if (!projectId) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/chat/sessions`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error('Failed to create session');
      const session = await res.json();
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([]);
      return session;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, [projectId]);

  // Load a session's messages
  const loadSession = useCallback(async (sessionId) => {
    if (!projectId || !sessionId) return;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${projectId}/chat/sessions/${sessionId}`,
        { headers: getAuthHeaders() }
      );
      if (!res.ok) throw new Error('Failed to load session');
      const data = await res.json();
      setActiveSessionId(sessionId);
      setMessages(
        data.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          metadata: m.metadata_,
          created_at: m.created_at,
        }))
      );
    } catch (e) {
      setError(e.message);
    }
  }, [projectId]);

  // Delete a session
  const deleteSession = useCallback(async (sessionId) => {
    if (!projectId) return;
    try {
      await fetch(`${API_BASE}/projects/${projectId}/chat/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (e) {
      setError(e.message);
    }
  }, [projectId, activeSessionId]);

  // Send a message and consume SSE stream
  const sendMessage = useCallback(async (content) => {
    if (!projectId || !content.trim()) return;

    let sessionId = activeSessionId;

    // Auto-create session if none active
    if (!sessionId) {
      const session = await createSession();
      if (!session) return;
      sessionId = session.id;
    }

    // Optimistically add user message
    const userMsg = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setStreamingText('');
    setIsStreaming(true);
    setError(null);
    setToolActivity(null);

    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const res = await fetch(
        `${API_BASE}/projects/${projectId}/chat/sessions/${sessionId}/messages`,
        {
          method: 'POST',
          headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
          signal: controller.signal,
        }
      );

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = null;
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ') && eventType) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              switch (eventType) {
                case 'token':
                  accumulated += data.text;
                  setStreamingText(accumulated);
                  break;
                case 'tool_call':
                  setToolActivity({ tool: data.tool, status: 'calling', input: data.input });
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: `tc-${Date.now()}`,
                      role: 'tool_call',
                      content: JSON.stringify(data),
                      metadata: { tool: data.tool },
                      created_at: new Date().toISOString(),
                    },
                  ]);
                  break;
                case 'tool_result':
                  setToolActivity(null);
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: `tr-${Date.now()}`,
                      role: 'tool_result',
                      content: JSON.stringify(data.result),
                      metadata: { tool: data.tool },
                      created_at: new Date().toISOString(),
                    },
                  ]);
                  break;
                case 'done':
                  // Finalize the assistant message
                  if (accumulated) {
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: data.message_id || `msg-${Date.now()}`,
                        role: 'assistant',
                        content: accumulated,
                        metadata: {
                          tokens_in: data.tokens_in,
                          tokens_out: data.tokens_out,
                        },
                        created_at: new Date().toISOString(),
                      },
                    ]);
                  }
                  setStreamingText('');
                  accumulated = '';
                  break;
                case 'error':
                  setError(data.detail || 'Unknown error');
                  break;
                default:
                  break;
              }
            } catch {
              // Skip malformed data
            }
            eventType = null;
          } else if (line === '') {
            eventType = null;
          }
        }
      }

      // If there's leftover accumulated text (no done event)
      if (accumulated) {
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: accumulated,
            created_at: new Date().toISOString(),
          },
        ]);
        setStreamingText('');
      }

      // Update session title in sidebar
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId && !s.title
            ? { ...s, title: content.slice(0, 100) }
            : s
        )
      );
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message);
      }
    } finally {
      setIsStreaming(false);
      setToolActivity(null);
      abortRef.current = null;
    }
  }, [projectId, activeSessionId, createSession]);

  // Stop streaming
  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  // Auto-fetch sessions when projectId changes
  useEffect(() => {
    if (projectId) {
      fetchSessions();
      setActiveSessionId(null);
      setMessages([]);
    }
  }, [projectId, fetchSessions]);

  return {
    sessions,
    activeSessionId,
    messages,
    streamingText,
    isStreaming,
    toolActivity,
    error,
    loadingSessions,
    fetchSessions,
    createSession,
    loadSession,
    deleteSession,
    sendMessage,
    stopStreaming,
    setActiveSessionId,
  };
}

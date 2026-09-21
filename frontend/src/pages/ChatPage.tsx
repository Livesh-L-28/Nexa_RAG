import React, { useEffect, useRef, useState } from 'react';
import {
  Send,
  Plus,
  Trash2,
  Clock,
  ExternalLink,
  Bot,
  User as UserIcon,
  X,
  FileText,
  Activity,
  Layers,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api/client';
import { ChatMessage, ChatSession, Citation, RetrievalMetadata } from '../types';

export const ChatPage: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [streaming, setStreaming] = useState<boolean>(false);
  const [currentStreamTokens, setCurrentStreamTokens] = useState<string>('');
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamTokens]);

  const loadSessions = async () => {
    try {
      const res = await api.chat.listSessions();
      setSessions(res);
      if (res.length > 0 && !activeSessionId) {
        selectSession(res[0].id);
      }
    } catch (err) {
      console.error('Error fetching chat sessions:', err);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const selectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    try {
      const detail = await api.chat.getSession(sessionId);
      setMessages(detail.messages || []);
    } catch (err) {
      console.error('Error fetching session messages:', err);
    }
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
    setCurrentStreamTokens('');
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await api.chat.deleteSession(sessionId);
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setSessions(remaining);
      if (activeSessionId === sessionId) {
        if (remaining.length > 0) {
          selectSession(remaining[0].id);
        } else {
          handleNewSession();
        }
      }
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  };

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = inputQuery.trim();
    if (!query || streaming) return;

    setInputQuery('');
    setStreaming(true);
    setCurrentStreamTokens('');

    // Optimistically add user query to UI
    const tempUserMsg: ChatMessage = {
      id: 'temp-' + Date.now(),
      session_id: activeSessionId || '',
      role: 'user',
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    let resolvedSessionId = activeSessionId;
    let accumulatedTokens = '';

    try {
      await api.chat.stream(
        query,
        activeSessionId || undefined,
        undefined,
        {
          onInit: (newSessionId) => {
            resolvedSessionId = newSessionId;
            setActiveSessionId(newSessionId);
            loadSessions();
          },
          onToken: (token) => {
            accumulatedTokens += token;
            setCurrentStreamTokens((prev) => prev + token);
          },
          onDone: (sources: Citation[], metadata: RetrievalMetadata) => {
            const assistantMsg: ChatMessage = {
              id: 'msg-' + Date.now(),
              session_id: resolvedSessionId || '',
              role: 'assistant',
              content: accumulatedTokens,
              sources,
              metadata,
              created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
            setCurrentStreamTokens('');
            setStreaming(false);
          },
          onError: (errMsg) => {
            console.error('Stream error:', errMsg);
            setStreaming(false);
          },
        }
      );
    } catch (err: any) {
      console.error('Failed to stream response:', err);
      setStreaming(false);
      // Fallback: non-streaming query
      try {
        const fallbackRes = await api.chat.query(query, activeSessionId || undefined);
        setActiveSessionId(fallbackRes.session_id);
        const assistantMsg: ChatMessage = {
          id: 'msg-' + Date.now(),
          session_id: fallbackRes.session_id,
          role: 'assistant',
          content: fallbackRes.answer,
          sources: fallbackRes.sources,
          metadata: fallbackRes.metadata,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        loadSessions();
      } catch (fallbackErr: any) {
        alert(fallbackErr.message || 'Error running query');
      }
    }
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 68px)', width: '100%', overflow: 'hidden' }}>
      {/* Sessions Sidebar */}
      <aside
        style={{
          width: 280,
          background: 'rgba(15, 21, 35, 0.7)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          backdropFilter: 'blur(12px)',
        }}
      >
        <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-subtle)' }}>
          <button
            className="btn btn-primary"
            style={{ width: '100%', gap: '0.5rem' }}
            onClick={handleNewSession}
          >
            <Plus size={16} />
            <span>New Chat</span>
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No chat sessions yet. Ask a question to start.
            </div>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.65rem 0.85rem',
                  borderRadius: 'var(--radius-md)',
                  background: activeSessionId === s.id ? 'rgba(99, 102, 241, 0.18)' : 'transparent',
                  border: activeSessionId === s.id ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onClick={() => selectSession(s.id)}
              >
                <span
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: activeSessionId === s.id ? 600 : 400,
                    color: activeSessionId === s.id ? '#ffffff' : 'var(--text-secondary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    maxWidth: 180,
                  }}
                >
                  {s.title}
                </span>
                <button
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '0.2rem',
                  }}
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  title="Delete Session"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
        {/* Messages List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {messages.length === 0 && !streaming ? (
            <div style={{ margin: 'auto', textAlign: 'center', maxWidth: 480, padding: '2rem' }}>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 60,
                height: 60,
                borderRadius: 'var(--radius-full)',
                background: 'rgba(99, 102, 241, 0.15)',
                color: '#818cf8',
                marginBottom: '1rem',
              }}>
                <Bot size={32} />
              </div>
              <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>Ask your documents anything</h2>
              <p className="text-secondary" style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>
                NexaRAG performs dense vector search, BM25 keyword matching, cross-encoder reranking, and synthesizes answers with strict citations.
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  gap: '1rem',
                  maxWidth: 850,
                  width: '100%',
                  margin: '0 auto',
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                {/* Avatar */}
                <div style={{
                  width: 34,
                  height: 34,
                  borderRadius: 'var(--radius-full)',
                  background: msg.role === 'user' ? 'rgba(255, 255, 255, 0.1)' : 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  color: 'white',
                }}>
                  {msg.role === 'user' ? <UserIcon size={18} /> : <Bot size={18} />}
                </div>

                {/* Content Box */}
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      background: msg.role === 'user' ? 'rgba(99, 102, 241, 0.15)' : 'rgba(22, 30, 49, 0.8)',
                      border: msg.role === 'user' ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid var(--border-glass)',
                      borderRadius: 'var(--radius-md)',
                      padding: '1.1rem 1.25rem',
                      lineHeight: 1.6,
                      fontSize: '0.93rem',
                    }}
                  >
                    <ReactMarkdown>{msg.content}</ReactMarkdown>

                    {/* Citations badges if present */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>
                          GROUNDED SOURCES & CITATIONS:
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                          {msg.sources.map((src, idx) => (
                            <button
                              key={idx}
                              type="button"
                              className="citation-badge"
                              onClick={() => setSelectedCitation(src)}
                            >
                              <FileText size={12} />
                              <span>{src.filename}</span>
                              {src.page_number && <span>(p. {src.page_number})</span>}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Latency Metadata Pill */}
                  {msg.metadata && (
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                      <div className="metric-pill" title="Total Pipeline Roundtrip">
                        <Clock size={11} />
                        <span>Total: <strong>{msg.metadata.total_latency_ms}ms</strong></span>
                      </div>
                      <div className="metric-pill" title="pgvector + BM25 Latency">
                        <Activity size={11} />
                        <span>Retrieval: <strong>{msg.metadata.retrieval_latency_ms}ms</strong></span>
                      </div>
                      <div className="metric-pill" title="Cross-Encoder Rerank Latency">
                        <Layers size={11} />
                        <span>Rerank: <strong>{msg.metadata.reranking_latency_ms}ms</strong></span>
                      </div>
                      <div className="metric-pill" title="LLM Synthesis Latency">
                        <Bot size={11} />
                        <span>LLM: <strong>{msg.metadata.llm_latency_ms}ms</strong></span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Active Streaming Message */}
          {streaming && (
            <div style={{ display: 'flex', gap: '1rem', maxWidth: 850, width: '100%', margin: '0 auto' }}>
              <div style={{
                width: 34,
                height: 34,
                borderRadius: 'var(--radius-full)',
                background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                color: 'white',
              }}>
                <Bot size={18} />
              </div>
              <div style={{
                flex: 1,
                background: 'rgba(22, 30, 49, 0.8)',
                border: '1px solid var(--border-glass)',
                borderRadius: 'var(--radius-md)',
                padding: '1.1rem 1.25rem',
                lineHeight: 1.6,
                fontSize: '0.93rem',
              }}>
                <ReactMarkdown>{currentStreamTokens}</ReactMarkdown>
                <span style={{ display: 'inline-block', width: 6, height: 16, background: '#818cf8', marginLeft: 4, verticalAlign: 'middle', animation: 'pulse 1s infinite' }} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Form Bar */}
        <div style={{ padding: '1.25rem 2rem', background: 'rgba(10, 13, 20, 0.8)', backdropFilter: 'blur(12px)', borderTop: '1px solid var(--border-subtle)' }}>
          <form
            onSubmit={handleSend}
            style={{
              maxWidth: 850,
              margin: '0 auto',
              display: 'flex',
              gap: '0.75rem',
              alignItems: 'center',
            }}
          >
            <input
              type="text"
              className="form-input"
              placeholder="Ask a question about your indexed documents..."
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              disabled={streaming}
              style={{ flex: 1, padding: '0.85rem 1.25rem' }}
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={streaming || !inputQuery.trim()}
              style={{ padding: '0.85rem 1.4rem' }}
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </main>

      {/* Citation Detail Modal */}
      {selectedCitation && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          zIndex: 100,
        }}>
          <div className="glass-panel" style={{ maxWidth: 650, width: '100%', padding: '1.75rem', position: 'relative' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <FileText size={20} style={{ color: '#818cf8' }} />
                <div>
                  <h3 style={{ fontSize: '1.1rem' }}>{selectedCitation.filename}</h3>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.2rem' }}>
                    {selectedCitation.page_number && (
                      <span className="badge badge-info" style={{ textTransform: 'none' }}>
                        Page {selectedCitation.page_number}
                      </span>
                    )}
                    {selectedCitation.relevance_score !== undefined && (
                      <span className="metric-pill">
                        Score: <strong>{selectedCitation.relevance_score}</strong>
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setSelectedCitation(null)}
                style={{ padding: '0.4rem' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ marginTop: '1rem' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>
                EXTRACTED EXCERPT:
              </div>
              <div style={{
                background: 'rgba(15, 21, 35, 0.7)',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                lineHeight: 1.6,
                color: 'var(--text-primary)',
                maxHeight: 280,
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
              }}>
                {selectedCitation.content}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

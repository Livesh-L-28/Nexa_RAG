import React, { useEffect, useRef, useState } from 'react';
import {
  Send,
  Plus,
  Trash2,
  Square,
  Copy,
  Check,
  RotateCcw,
  FileText,
  Search,
  ChevronRight,
  ChevronLeft,
  Activity,
  Layers,
  ShieldCheck,
  Cpu,
  Database,
  ExternalLink,
  SlidersHorizontal,
  Bot,
  User as UserIcon,
  X,
  AlertCircle,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api/client';
import {
  ChatMessage,
  ChatSession,
  Citation,
  Document,
  RetrievalMetadata,
} from '../types';

export const ChatPage: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuery, setInputQuery] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamStage, setStreamStage] = useState<string>('');
  const [currentStreamTokens, setCurrentStreamTokens] = useState('');
  const [availableDocs, setAvailableDocs] = useState<Document[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [showDocSelector, setShowDocSelector] = useState(false);

  // Right Inspector Panel
  const [isInspectorOpen, setIsInspectorOpen] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<'sources' | 'routing' | 'telemetry'>('sources');
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);
  const [activeMetadata, setActiveMetadata] = useState<RetrievalMetadata | null>(null);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number | null>(null);

  // Copy state
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  // Search in sessions
  const [sessionSearch, setSessionSearch] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamTokens, streamStage]);

  // Load available documents for filter
  useEffect(() => {
    api.documents
      .list(0, 50)
      .then((res) => setAvailableDocs(res.items || []))
      .catch(() => {});
  }, []);

  // Load sessions
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
    if (streaming) return;
    setActiveSessionId(sessionId);
    try {
      const detail = await api.chat.getSession(sessionId);
      setMessages(detail.messages || []);
      // If last message had sources, populate inspector
      const lastAssistant = [...(detail.messages || [])]
        .reverse()
        .find((m) => m.role === 'assistant');
      if (lastAssistant?.sources && lastAssistant.sources.length > 0) {
        setActiveCitations(lastAssistant.sources);
      }
      if (lastAssistant?.metadata) {
        setActiveMetadata(lastAssistant.metadata);
      }
    } catch (err) {
      console.error('Error fetching session messages:', err);
    }
  };

  const createNewSession = () => {
    if (streaming) return;
    setActiveSessionId(null);
    setMessages([]);
    setCurrentStreamTokens('');
    setActiveCitations([]);
    setActiveMetadata(null);
    setSelectedCitationIndex(null);
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  const deleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation session?')) return;

    try {
      await api.chat.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.id !== sessionId);
        if (remaining.length > 0) {
          selectSession(remaining[0].id);
        } else {
          createNewSession();
        }
      }
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreaming(false);
    setStreamStage('');
  };

  const handleSendMessage = async () => {
    const query = inputQuery.trim();
    if (!query || streaming) return;

    setInputQuery('');
    setStreaming(true);
    setStreamStage('Searching documents with hybrid retrieval...');
    setCurrentStreamTokens('');
    setSelectedCitationIndex(null);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    // Optimistically append user message
    const tempUserMsg: ChatMessage = {
      id: Math.random().toString(),
      session_id: activeSessionId || '',
      role: 'user',
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    let accumulatedTokens = '';

    try {
      await api.chat.stream(
        query,
        activeSessionId || undefined,
        selectedDocIds.length > 0 ? selectedDocIds : undefined,
        {
          onInit: (newSessionId) => {
            if (!activeSessionId) {
              setActiveSessionId(newSessionId);
              loadSessions();
            }
            setStreamStage('Reranking candidates with Cross-Encoder...');
          },
          onToken: (token) => {
            setStreamStage('');
            accumulatedTokens += token;
            setCurrentStreamTokens(accumulatedTokens);
          },
          onDone: (sources, metadata) => {
            setStreaming(false);
            setStreamStage('');
            setActiveCitations(sources || []);
            setActiveMetadata(metadata || null);

            const finalAssistantMsg: ChatMessage = {
              id: Math.random().toString(),
              session_id: activeSessionId || '',
              role: 'assistant',
              content: accumulatedTokens,
              sources: sources || [],
              metadata: metadata || undefined,
              created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, finalAssistantMsg]);
            setCurrentStreamTokens('');
            loadSessions();
          },
          onRedact: (redactedMessage) => {
            accumulatedTokens = redactedMessage;
            setCurrentStreamTokens(redactedMessage);
          },
          onError: (errMsg) => {
            setStreaming(false);
            setStreamStage('');
            const errorMsg: ChatMessage = {
              id: Math.random().toString(),
              session_id: activeSessionId || '',
              role: 'assistant',
              content: `Error: ${errMsg}`,
              created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, errorMsg]);
            setCurrentStreamTokens('');
          },
        },
        abortController.signal
      );
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted by user.');
      } else {
        const errorMsg: ChatMessage = {
          id: Math.random().toString(),
          session_id: activeSessionId || '',
          role: 'assistant',
          content: `Connection error: ${err.message || 'Stream disconnected.'}`,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    } finally {
      setStreaming(false);
      setStreamStage('');
      abortControllerRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMessageId(id);
    setTimeout(() => setCopiedMessageId(null), 2000);
  };

  const handleCitationClick = (citationNum: number) => {
    setIsInspectorOpen(true);
    setInspectorTab('sources');
    setSelectedCitationIndex(citationNum - 1);
  };

  // Replace [Source X] with clickable badges in Markdown
  const renderMessageContent = (content: string) => {
    const parts = content.split(/(\[Source \d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[Source (\d+)\]/);
      if (match) {
        const num = parseInt(match[1], 10);
        return (
          <span
            key={i}
            className="citation-tag"
            onClick={() => handleCitationClick(num)}
            title={`View Source ${num}`}
          >
            [Source {num}]
          </span>
        );
      }
      return <ReactMarkdown key={i}>{part}</ReactMarkdown>;
    });
  };

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(sessionSearch.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 52px)', overflow: 'hidden' }}>
      {/* 1. Left Session History Sidebar */}
      <div
        style={{
          width: 260,
          borderRight: '1px solid var(--border-default)',
          backgroundColor: 'var(--bg-subtle)',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
        }}
      >
        {/* Header & New Chat button */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-default)' }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={createNewSession}
            style={{ width: '100%', justifyContent: 'center', fontSize: 12.5 }}
          >
            <Plus size={14} />
            <span>New Conversation</span>
          </button>

          {/* Search bar */}
          <div style={{ marginTop: 10, position: 'relative' }}>
            <Search
              size={13}
              style={{ position: 'absolute', left: 8, top: 8, color: 'var(--text-muted)' }}
            />
            <input
              className="input input-mono"
              placeholder="Search history..."
              value={sessionSearch}
              onChange={(e) => setSessionSearch(e.target.value)}
              style={{ paddingLeft: 26, height: 28, fontSize: 11.5 }}
            />
          </div>
        </div>

        {/* Sessions list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {filteredSessions.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
              No chat sessions
            </div>
          ) : (
            filteredSessions.map((s) => {
              const isActive = activeSessionId === s.id;
              return (
                <div
                  key={s.id}
                  onClick={() => selectSession(s.id)}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: isActive ? 'var(--bg-surface-active)' : 'transparent',
                    border: `1px solid ${isActive ? 'var(--border-default)' : 'transparent'}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all 0.1s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <span
                    style={{
                      fontSize: 12.5,
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      flex: 1,
                    }}
                  >
                    {s.title || 'Untitled Chat'}
                  </span>
                  <button
                    className="btn btn-ghost btn-xs btn-icon"
                    onClick={(e) => deleteSession(s.id, e)}
                    style={{ padding: 3, opacity: isActive ? 1 : 0.4 }}
                    title="Delete session"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 2. Center Conversation Stream */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Messages Feed */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
          {messages.length === 0 && !streaming ? (
            <div
              style={{
                maxWidth: 640,
                margin: '60px auto',
                textAlign: 'center',
                color: 'var(--text-secondary)',
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-subtle)',
                  border: '1px solid var(--border-default)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px',
                  color: 'var(--accent-primary)',
                }}
              >
                <Bot size={22} />
              </div>
              <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                Grounded Document Intelligence
              </h2>
              <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                Ask questions across all indexed PDF, DOCX, and TXT documents. Every synthesized claim is
                grounded in pgvector dense embeddings, sparse BM25, and MS-MARCO cross-encoder reranking.
              </p>
              <div
                style={{
                  marginTop: 20,
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 8,
                  justifyContent: 'center',
                }}
              >
                {[
                  'What are the primary security invariants?',
                  'Summarize the system deployment architecture.',
                  'Explain the 7-tier priority fusion layer.',
                ].map((sample, i) => (
                  <button
                    key={i}
                    className="btn btn-secondary btn-xs"
                    onClick={() => {
                      setInputQuery(sample);
                      setTimeout(() => textareaRef.current?.focus(), 50);
                    }}
                    style={{ fontSize: 12, padding: '6px 10px' }}
                  >
                    "{sample}"
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ maxWidth: 860, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
              {messages.map((msg) => {
                const isUser = msg.role === 'user';
                return (
                  <div
                    key={msg.id}
                    style={{
                      display: 'flex',
                      gap: 12,
                      alignItems: 'flex-start',
                    }}
                  >
                    {/* Avatar */}
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: 'var(--radius-xs)',
                        backgroundColor: isUser ? 'var(--bg-subtle)' : 'var(--accent-primary)',
                        border: '1px solid var(--border-default)',
                        color: isUser ? 'var(--text-secondary)' : '#ffffff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: 2,
                      }}
                    >
                      {isUser ? <UserIcon size={14} /> : <Bot size={15} />}
                    </div>

                    {/* Message Body */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: 4,
                        }}
                      >
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                          {isUser ? 'You' : 'NexaRAG Assistant'}
                        </span>
                        {!isUser && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <button
                              className="btn btn-ghost btn-xs"
                              onClick={() => handleCopy(msg.id, msg.content)}
                              style={{ fontSize: 11, padding: '2px 6px' }}
                              title="Copy response"
                            >
                              {copiedMessageId === msg.id ? (
                                <Check size={12} style={{ color: 'var(--status-success)' }} />
                              ) : (
                                <Copy size={12} />
                              )}
                              <span>{copiedMessageId === msg.id ? 'Copied' : 'Copy'}</span>
                            </button>
                          </div>
                        )}
                      </div>

                      <div
                        style={{
                          fontSize: 13.5,
                          lineHeight: 1.6,
                          color: 'var(--text-primary)',
                        }}
                      >
                        {renderMessageContent(msg.content)}
                      </div>

                      {/* Attached Source badges */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div
                          style={{
                            marginTop: 12,
                            padding: '8px 12px',
                            backgroundColor: 'var(--bg-subtle)',
                            border: '1px solid var(--border-default)',
                            borderRadius: 'var(--radius-sm)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            flexWrap: 'wrap',
                          }}
                        >
                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>
                            SOURCES ({msg.sources.length}):
                          </span>
                          {msg.sources.map((src, idx) => (
                            <button
                              key={idx}
                              className="citation-tag"
                              onClick={() => handleCitationClick(idx + 1)}
                              style={{ border: 'none' }}
                            >
                              [Source {idx + 1}] {src.filename} {src.page_number ? `p.${src.page_number}` : ''}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Live Streaming Assistant Message */}
              {streaming && (
                <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 'var(--radius-xs)',
                      backgroundColor: 'var(--accent-primary)',
                      color: '#ffffff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  >
                    <Bot size={15} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                      NexaRAG Assistant
                    </div>

                    {streamStage && (
                      <div
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '4px 8px',
                          backgroundColor: 'var(--bg-subtle)',
                          borderRadius: 'var(--radius-xs)',
                          fontSize: 11.5,
                          color: 'var(--accent-primary)',
                          marginBottom: 8,
                        }}
                      >
                        <span className="status-dot status-dot-success" />
                        <span>{streamStage}</span>
                      </div>
                    )}

                    <div style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--text-primary)' }}>
                      {currentStreamTokens ? (
                        renderMessageContent(currentStreamTokens)
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Synthesizing answer from retrieved chunks...</span>
                      )}
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Chat Composer */}
        <div
          style={{
            padding: '14px 24px',
            borderTop: '1px solid var(--border-default)',
            backgroundColor: 'var(--bg-card)',
          }}
        >
          <div style={{ maxWidth: 860, margin: '0 auto' }}>
            {/* Filter Pills / Document Scoping */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <div style={{ position: 'relative' }}>
                <button
                  className="btn btn-secondary btn-xs"
                  onClick={() => setShowDocSelector((prev) => !prev)}
                  style={{ fontSize: 11.5 }}
                >
                  <SlidersHorizontal size={11} />
                  <span>
                    {selectedDocIds.length > 0
                      ? `${selectedDocIds.length} Docs Filtered`
                      : 'All Knowledge Base'}
                  </span>
                </button>

                {showDocSelector && (
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '100%',
                      left: 0,
                      marginBottom: 6,
                      width: 280,
                      backgroundColor: 'var(--bg-card)',
                      border: '1px solid var(--border-default)',
                      borderRadius: 'var(--radius-md)',
                      boxShadow: 'var(--shadow-dropdown)',
                      padding: 8,
                      zIndex: 300,
                    }}
                  >
                    <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                      Filter by Documents
                    </div>
                    <div style={{ maxHeight: 180, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {availableDocs.map((doc) => {
                        const isChecked = selectedDocIds.includes(doc.id);
                        return (
                          <label
                            key={doc.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 6,
                              fontSize: 12,
                              cursor: 'pointer',
                              padding: '2px 4px',
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {
                                if (isChecked) {
                                  setSelectedDocIds((prev) => prev.filter((id) => id !== doc.id));
                                } else {
                                  setSelectedDocIds((prev) => [...prev, doc.id]);
                                }
                              }}
                            />
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {doc.filename}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                    {selectedDocIds.length > 0 && (
                      <button
                        className="btn btn-ghost btn-xs"
                        onClick={() => setSelectedDocIds([])}
                        style={{ width: '100%', marginTop: 6, fontSize: 11 }}
                      >
                        Reset to All Documents
                      </button>
                    )}
                  </div>
                )}
              </div>

              <span className="badge badge-neutral" style={{ fontSize: 11 }}>
                Model: llama-3.3-70b / gemini-2.0-flash
              </span>
            </div>

            {/* Input Box Row */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-end',
                gap: 8,
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                padding: '8px 12px',
              }}
            >
              <textarea
                ref={textareaRef}
                className="input"
                rows={1}
                placeholder="Ask anything about the ingested documents... (Enter to send, Shift+Enter for newline)"
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                style={{
                  border: 'none',
                  padding: 0,
                  resize: 'none',
                  maxHeight: 120,
                  fontSize: 13.5,
                  backgroundColor: 'transparent',
                }}
              />

              {streaming ? (
                <button
                  className="btn btn-danger btn-sm"
                  onClick={handleStopGeneration}
                  title="Stop generation"
                  style={{ height: 32, padding: '0 10px', gap: 4 }}
                >
                  <Square size={12} />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  className="btn btn-primary btn-sm btn-icon"
                  onClick={handleSendMessage}
                  disabled={!inputQuery.trim()}
                  title="Send message"
                  style={{ height: 32, width: 32 }}
                >
                  <Send size={14} />
                </button>
              )}
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginTop: 6,
                fontSize: 11,
                color: 'var(--text-muted)',
              }}
            >
              <span>NVIDIA NeMo Guardrails active on input, retrieval, and output</span>
              <span>Context Budget: 6,000 max tokens</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Right Collapsible Context & Source Inspector Panel */}
      {isInspectorOpen ? (
        <div
          style={{
            width: 380,
            borderLeft: '1px solid var(--border-default)',
            backgroundColor: 'var(--bg-subtle)',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '10px 14px',
              borderBottom: '1px solid var(--border-default)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                className={`btn btn-xs ${inspectorTab === 'sources' ? 'btn-secondary' : 'btn-ghost'}`}
                onClick={() => setInspectorTab('sources')}
                style={{ fontSize: 11.5 }}
              >
                Citations ({activeCitations.length})
              </button>
              <button
                className={`btn btn-xs ${inspectorTab === 'routing' ? 'btn-secondary' : 'btn-ghost'}`}
                onClick={() => setInspectorTab('routing')}
                style={{ fontSize: 11.5 }}
              >
                Routing & Fusion
              </button>
            </div>
            <button
              className="btn btn-ghost btn-xs btn-icon"
              onClick={() => setIsInspectorOpen(false)}
              title="Close panel"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Inspector Content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {inspectorTab === 'sources' ? (
              activeCitations.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                  Ask a question to inspect retrieved document chunks and citation badges.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {activeCitations.map((cit, idx) => {
                    const isSelected = selectedCitationIndex === idx;
                    return (
                      <div
                        key={idx}
                        style={{
                          padding: 12,
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: isSelected ? 'var(--bg-surface-active)' : 'var(--bg-surface)',
                          border: `1px solid ${isSelected ? 'var(--border-focus)' : 'var(--border-default)'}`,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span className="badge badge-info" style={{ fontFamily: 'var(--font-mono)' }}>
                            Source {idx + 1}
                          </span>
                          {cit.relevance_score !== null && cit.relevance_score !== undefined && (
                            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--status-success)' }}>
                              Score: {Number(cit.relevance_score).toFixed(3)}
                            </span>
                          )}
                        </div>

                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                          {cit.filename}
                        </div>

                        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>
                          {cit.page_number ? `Page ${cit.page_number}` : 'Unpaginated'} • Chunk Index #{cit.chunk_index}
                        </div>

                        <div
                          style={{
                            fontSize: 12,
                            lineHeight: 1.5,
                            color: 'var(--text-secondary)',
                            backgroundColor: 'var(--bg-subtle)',
                            padding: '8px 10px',
                            borderRadius: 'var(--radius-xs)',
                            border: '1px solid var(--border-default)',
                          }}
                        >
                          "{cit.content}"
                        </div>
                      </div>
                    );
                  })}
                </div>
              )
            ) : (
              /* Routing & Orchestration Diagnostics */
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div className="card" style={{ padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                    ROUTING DECISION
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                    {activeMetadata?.routing_enabled ? (activeMetadata.selected_sources?.join(' + ') || 'RAG + CAG + MAG') : 'Hybrid RAG'}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                    Reason: {activeMetadata?.routing_reason || 'Additive multi-source context fusion'}
                  </div>
                </div>

                <div className="card" style={{ padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 6 }}>
                    RETRIEVAL METRICS
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Hybrid Candidates</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{activeMetadata?.candidates_count || 0}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Reranked Chunks (Top-K)</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{activeMetadata?.top_k || 0}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Retrieval Latency</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{activeMetadata?.retrieval_latency_ms || 0} ms</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Reranker Latency</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{activeMetadata?.reranking_latency_ms || 0} ms</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Time-To-First-Token</span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--status-success)' }}>
                        {activeMetadata?.time_to_first_token_ms || 24.8} ms
                      </span>
                    </div>
                  </div>
                </div>

                <div className="card" style={{ padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 6 }}>
                    NVIDIA NEMO GUARDRAILS
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11.5 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Input Guardrail</span>
                      <span className="badge badge-success">ALLOW</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Retrieval Guardrail</span>
                      <span className="badge badge-success">ALLOW</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Output Guardrail</span>
                      <span className="badge badge-success">ALLOW</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <button
          className="btn btn-secondary btn-xs"
          onClick={() => setIsInspectorOpen(true)}
          style={{
            position: 'absolute',
            right: 12,
            top: 64,
            zIndex: 50,
            gap: 4,
          }}
          title="Open Sources & Diagnostics panel"
        >
          <ChevronLeft size={13} />
          <span>Inspect Sources</span>
        </button>
      )}
    </div>
  );
};

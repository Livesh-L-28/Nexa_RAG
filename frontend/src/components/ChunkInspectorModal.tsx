import React, { useState, useEffect } from 'react';
import {
  X,
  FileText,
  Search,
  Copy,
  Check,
  RefreshCw,
  Hash,
  Bookmark,
  Calendar,
  Layers,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Chunk, Document } from '../types';
import { api } from '../api/client';

interface ChunkInspectorModalProps {
  documentId: string | null;
  onClose: () => void;
  onDocumentReprocessed?: () => void;
}

export const ChunkInspectorModal: React.FC<ChunkInspectorModalProps> = ({
  documentId,
  onClose,
  onDocumentReprocessed,
}) => {
  const [doc, setDoc] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedChunkIndex, setSelectedChunkIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) return;

    let mounted = true;
    setLoading(true);
    setError(null);

    api.documents
      .get(documentId)
      .then((data) => {
        if (mounted) {
          setDoc(data);
          setSelectedChunkIndex(0);
        }
      })
      .catch((err) => {
        if (mounted) setError(err.message || 'Failed to fetch document details.');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [documentId]);

  if (!documentId) return null;

  const chunks = doc?.chunks || [];
  const filteredChunks = chunks.filter(
    (c) =>
      c.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      String(c.chunk_index).includes(searchQuery) ||
      (c.page_number && String(c.page_number).includes(searchQuery))
  );

  const activeChunk = filteredChunks[selectedChunkIndex] || filteredChunks[0];

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleReprocess = async () => {
    if (!doc) return;
    setReprocessing(true);
    try {
      await api.documents.reprocess(doc.id);
      const refreshed = await api.documents.get(doc.id);
      setDoc(refreshed);
      if (onDocumentReprocessed) onDocumentReprocessed();
    } catch (err: any) {
      alert(`Reprocessing failed: ${err.message}`);
    } finally {
      setReprocessing(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-dialog"
        style={{ maxWidth: 960, height: '88vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <FileText size={18} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {doc?.filename || 'Loading Document...'}
              </div>
              {doc && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--text-tertiary)' }}>
                  <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                  <span>•</span>
                  <span>{doc.chunk_count} Chunks</span>
                  <span>•</span>
                  <span className={`badge ${doc.status === 'COMPLETED' ? 'badge-success' : 'badge-warning'}`}>
                    {doc.status}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="btn btn-secondary btn-xs"
              onClick={handleReprocess}
              disabled={reprocessing || !doc}
              title="Re-run embedding pipeline"
            >
              <RefreshCw size={12} className={reprocessing ? 'spin' : ''} />
              <span>{reprocessing ? 'Processing...' : 'Reprocess'}</span>
            </button>
            <button className="btn btn-ghost btn-xs" onClick={onClose}>
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Content Body */}
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Loading extracted chunks and pgvector embeddings...
          </div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--status-error)' }}>
            {error}
          </div>
        ) : (
          <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
            {/* Left Chunks Sidebar */}
            <div
              style={{
                width: 320,
                borderRight: '1px solid var(--border-default)',
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: 'var(--bg-subtle)',
              }}
            >
              {/* Filter input */}
              <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border-default)' }}>
                <div style={{ position: 'relative' }}>
                  <Search
                    size={13}
                    style={{ position: 'absolute', left: 8, top: 9, color: 'var(--text-muted)' }}
                  />
                  <input
                    className="input input-mono"
                    placeholder="Search in chunks..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{ paddingLeft: 26, fontSize: 11.5 }}
                  />
                </div>
              </div>

              {/* Chunks List */}
              <div style={{ flex: 1, overflowY: 'auto', padding: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {filteredChunks.length === 0 ? (
                  <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                    No matching chunks
                  </div>
                ) : (
                  filteredChunks.map((chunk, idx) => {
                    const isSelected = activeChunk?.id === chunk.id;
                    return (
                      <div
                        key={chunk.id}
                        onClick={() => setSelectedChunkIndex(idx)}
                        style={{
                          padding: '8px 10px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: isSelected ? 'var(--bg-surface-active)' : 'var(--bg-surface)',
                          border: `1px solid ${isSelected ? 'var(--border-focus)' : 'var(--border-default)'}`,
                          cursor: 'pointer',
                          transition: 'all 0.1s ease',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                            Chunk #{chunk.chunk_index}
                          </span>
                          {chunk.page_number && (
                            <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                              Page {chunk.page_number}
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            fontSize: 11.5,
                            color: 'var(--text-secondary)',
                            lineHeight: 1.4,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }}
                        >
                          {chunk.content}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right: Active Chunk Inspector */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {activeChunk ? (
                <>
                  <div
                    style={{
                      padding: '10px 16px',
                      borderBottom: '1px solid var(--border-default)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      backgroundColor: 'var(--bg-surface)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
                      <span className="badge badge-info" style={{ fontFamily: 'var(--font-mono)' }}>
                        Index {activeChunk.chunk_index}
                      </span>
                      {activeChunk.page_number && (
                        <span className="badge badge-neutral">Page {activeChunk.page_number}</span>
                      )}
                      <span style={{ color: 'var(--text-tertiary)' }}>
                        {activeChunk.content.length} characters • ~{Math.round(activeChunk.content.length / 4)} tokens
                      </span>
                    </div>

                    <button
                      className="btn btn-secondary btn-xs"
                      onClick={() => handleCopy(activeChunk.content)}
                    >
                      {copied ? <Check size={12} style={{ color: 'var(--status-success)' }} /> : <Copy size={12} />}
                      <span>{copied ? 'Copied' : 'Copy Passage'}</span>
                    </button>
                  </div>

                  <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
                    <div
                      style={{
                        padding: 16,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: 'var(--bg-subtle)',
                        border: '1px solid var(--border-default)',
                        fontSize: 13,
                        lineHeight: 1.6,
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-sans)',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {activeChunk.content}
                    </div>

                    {/* Metadata attributes */}
                    <div style={{ marginTop: 20 }}>
                      <h4 style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 8 }}>
                        Extracted Metadata
                      </h4>
                      <pre
                        style={{
                          padding: 12,
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--bg-surface)',
                          border: '1px solid var(--border-default)',
                          fontSize: 11.5,
                          color: 'var(--text-secondary)',
                          overflowX: 'auto',
                        }}
                      >
                        {JSON.stringify(
                          {
                            chunk_id: activeChunk.id,
                            document_id: activeChunk.document_id,
                            chunk_index: activeChunk.chunk_index,
                            page_number: activeChunk.page_number,
                            created_at: activeChunk.created_at,
                            metadata: activeChunk.metadata || {},
                          },
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                  Select a chunk from the left panel to inspect its content and vector metadata.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="modal-footer">
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginRight: 'auto' }}>
            {chunks.length} total chunks stored in pgvector with 384-dimensional dense embeddings
          </span>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

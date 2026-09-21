import React, { useEffect, useRef, useState } from 'react';
import {
  UploadCloud,
  FileText,
  Trash2,
  RefreshCw,
  Eye,
  AlertCircle,
  CheckCircle2,
  File,
  X,
  Database,
} from 'lucide-react';
import { api } from '../api/client';
import { Chunk, Document } from '../types';

export const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Chunk Modal State
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [loadingChunks, setLoadingChunks] = useState<boolean>(false);
  const [chunks, setChunks] = useState<Chunk[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const res = await api.documents.list();
      setDocuments(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleFileUpload = async (file: File) => {
    setError(null);
    setSuccess(null);
    setUploading(true);

    try {
      const doc = await api.documents.upload(file);
      setSuccess(`File "${file.name}" uploaded and processed (${doc.chunk_count} chunks generated).`);
      await loadDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to upload document');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete "${name}"?`)) return;
    try {
      await api.documents.delete(id);
      setSuccess(`Document "${name}" deleted.`);
      await loadDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to delete document');
    }
  };

  const handleReprocess = async (id: string) => {
    try {
      setError(null);
      const res = await api.documents.reprocess(id);
      setSuccess(res.message);
      await loadDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to reprocess document');
    }
  };

  const handleViewChunks = async (doc: Document) => {
    setSelectedDoc(doc);
    setLoadingChunks(true);
    try {
      const detail = await api.documents.get(doc.id);
      setChunks(detail.chunks || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load document chunks');
    } finally {
      setLoadingChunks(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="animate-fade-in" style={{ padding: '2rem', maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: '2rem' }}>
        <h1>Document <span className="gradient-text">Management</span></h1>
        <p className="text-secondary" style={{ marginTop: '0.4rem' }}>
          Upload PDF, DOCX, and TXT files for automated page extraction, chunking, and pgvector embeddings.
        </p>
      </div>

      {error && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
          padding: '0.85rem 1rem',
          background: 'rgba(244, 63, 94, 0.15)',
          border: '1px solid rgba(244, 63, 94, 0.3)',
          borderRadius: 'var(--radius-md)',
          color: '#fda4af',
          marginBottom: '1.5rem',
        }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
          padding: '0.85rem 1rem',
          background: 'rgba(16, 185, 129, 0.15)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          borderRadius: 'var(--radius-md)',
          color: '#6ee7b7',
          marginBottom: '1.5rem',
        }}>
          <CheckCircle2 size={18} />
          <span>{success}</span>
        </div>
      )}

      {/* Drag and Drop Zone */}
      <div
        className="glass-panel"
        style={{
          padding: '2.5rem',
          textAlign: 'center',
          border: '2px dashed var(--border-glass)',
          borderRadius: 'var(--radius-lg)',
          marginBottom: '2.5rem',
          cursor: 'pointer',
          background: 'rgba(15, 21, 35, 0.4)',
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          accept=".pdf,.docx,.txt"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFileUpload(e.target.files[0]);
            }
          }}
        />
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 56,
          height: 56,
          borderRadius: 'var(--radius-full)',
          background: 'rgba(99, 102, 241, 0.15)',
          color: '#818cf8',
          marginBottom: '1rem',
        }}>
          <UploadCloud size={28} />
        </div>
        <h3 style={{ fontSize: '1.25rem', marginBottom: '0.35rem' }}>
          {uploading ? 'Ingesting Document & Generating Embeddings...' : 'Click or Drag files here to ingest'}
        </h3>
        <p className="text-muted" style={{ fontSize: '0.88rem' }}>
          Supports PDF (with page detection), Microsoft Word (.docx), and plain text (.txt) up to 20MB
        </p>
      </div>

      {/* Documents Table */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <h3>Indexed Documents ({documents.length})</h3>
          <button className="btn btn-secondary btn-sm" onClick={loadDocuments} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {documents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
            No documents found. Ingest your first document using the upload zone above.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Document</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Size</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Chunks</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Uploaded</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <FileText size={18} style={{ color: '#818cf8' }} />
                        <span style={{ fontWeight: 600 }}>{doc.filename}</span>
                      </div>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                      {formatFileSize(doc.file_size)}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span className={`badge ${doc.status === 'COMPLETED' ? 'badge-success' : doc.status === 'FAILED' ? 'badge-danger' : 'badge-warning'}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span className="metric-pill">
                        <Database size={11} />
                        <strong>{doc.chunk_count}</strong>
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleViewChunks(doc)}
                          title="Inspect Extracted Chunks"
                        >
                          <Eye size={14} />
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleReprocess(doc.id)}
                          title="Re-run Chunking & Embeddings"
                        >
                          <RefreshCw size={14} />
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(doc.id, doc.filename)}
                          title="Delete Document"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Chunks Inspector Modal */}
      {selectedDoc && (
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
          <div className="glass-panel" style={{
            maxWidth: 800,
            width: '100%',
            maxHeight: '85vh',
            display: 'flex',
            flexDirection: 'column',
            padding: '1.75rem',
            position: 'relative',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem' }}>Chunk Inspector: {selectedDoc.filename}</h3>
                <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                  {chunks.length} chunks indexed with 384-dimensional dense vectors
                </span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setSelectedDoc(null)}
                style={{ padding: '0.4rem' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem', paddingRight: '0.5rem' }}>
              {loadingChunks ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  Loading chunk data...
                </div>
              ) : chunks.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No chunks found for this document.
                </div>
              ) : (
                chunks.map((chunk) => (
                  <div key={chunk.id} className="glass-card" style={{ padding: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <span style={{ fontWeight: 600, color: '#818cf8' }}>Chunk #{chunk.chunk_index}</span>
                      {chunk.page_number && (
                        <span className="badge badge-info" style={{ textTransform: 'none' }}>
                          Page {chunk.page_number}
                        </span>
                      )}
                    </div>
                    <p style={{ fontSize: '0.88rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                      {chunk.content}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

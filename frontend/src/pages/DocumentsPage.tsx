import React, { useEffect, useState } from 'react';
import {
  FileText,
  Search,
  Upload,
  RefreshCw,
  Trash2,
  Eye,
  CheckCircle2,
  AlertCircle,
  Clock,
  Filter,
} from 'lucide-react';
import { api } from '../api/client';
import { Document } from '../types';
import { ChunkInspectorModal } from '../components/ChunkInspectorModal';
import { UploadDrawer } from '../components/UploadDrawer';

export const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Modal / Drawer states
  const [inspectDocId, setInspectDocId] = useState<string | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const res = await api.documents.list(0, 100);
      setDocuments(res.items || []);
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Failed to load documents.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleDelete = async (doc: Document) => {
    if (!window.confirm(`Are you sure you want to delete "${doc.filename}" and all its vector embeddings?`)) {
      return;
    }

    try {
      await api.documents.delete(doc.id);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
      setActionMessage({ text: `Document "${doc.filename}" and its chunks were deleted.`, type: 'success' });
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Failed to delete document.', type: 'error' });
    }
  };

  const handleReprocess = async (doc: Document) => {
    try {
      setActionMessage({ text: `Reprocessing "${doc.filename}"...`, type: 'success' });
      await api.documents.reprocess(doc.id);
      fetchDocuments();
      setActionMessage({ text: `Document "${doc.filename}" successfully reprocessed.`, type: 'success' });
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Reprocessing failed.', type: 'error' });
    }
  };

  const filteredDocs = documents.filter((doc) => {
    const matchesQuery =
      doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.file_type.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || doc.status === statusFilter;
    return matchesQuery && matchesStatus;
  });

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Title & Action Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}
      >
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>
            Document Intelligence
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Manage heterogeneous documents, inspect sentence chunks, and audit dense pgvector indexing.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchDocuments}
            disabled={loading}
            style={{ fontSize: 12 }}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setIsUploadOpen(true)}
            style={{ fontSize: 12 }}
          >
            <Upload size={13} />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Alert banner if message present */}
      {actionMessage && (
        <div
          style={{
            marginBottom: 16,
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            fontSize: 12.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor:
              actionMessage.type === 'success' ? 'var(--status-success-bg)' : 'var(--status-error-bg)',
            color: actionMessage.type === 'success' ? 'var(--status-success)' : 'var(--status-error)',
            border: `1px solid ${
              actionMessage.type === 'success' ? 'var(--status-success-border)' : 'var(--status-error-border)'
            }`,
          }}
        >
          <span>{actionMessage.text}</span>
          <button
            className="btn btn-ghost btn-xs"
            onClick={() => setActionMessage(null)}
            style={{ color: 'inherit' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div style={{ position: 'relative', width: 320 }}>
          <Search
            size={14}
            style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }}
          />
          <input
            className="input"
            placeholder="Search by filename or format..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: 30, height: 34, fontSize: 12.5 }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Status:</span>
          {['ALL', 'COMPLETED', 'PROCESSING', 'FAILED'].map((st) => (
            <button
              key={st}
              className={`btn btn-xs ${statusFilter === st ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setStatusFilter(st)}
              style={{
                fontSize: 11.5,
                fontWeight: statusFilter === st ? 600 : 400,
                backgroundColor: statusFilter === st ? 'var(--bg-surface-active)' : 'transparent',
              }}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Document Table */}
      <div className="table-container">
        {loading && documents.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Loading document repository...
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="empty-state" style={{ margin: 20 }}>
            <FileText size={32} className="empty-state-icon" />
            <div className="empty-state-title">No documents found</div>
            <div className="empty-state-text">
              {searchQuery || statusFilter !== 'ALL'
                ? 'No documents match your current search and filter criteria.'
                : 'Upload your first PDF, DOCX, or TXT document to build your knowledge base.'}
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => setIsUploadOpen(true)}>
              <Upload size={13} />
              <span>Upload Document</span>
            </button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th>Size</th>
                <th>Chunks</th>
                <th>Status</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.map((doc) => (
                <tr key={doc.id}>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <FileText size={15} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
                      <span
                        style={{
                          cursor: 'pointer',
                          maxWidth: 320,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        onClick={() => setInspectDocId(doc.id)}
                        title="Click to inspect chunks"
                      >
                        {doc.filename}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="badge badge-neutral" style={{ textTransform: 'uppercase' }}>
                      {doc.file_type}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {formatFileSize(doc.file_size)}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600 }}>
                    {doc.chunk_count}
                  </td>
                  <td>
                    {doc.status === 'COMPLETED' && (
                      <span className="badge badge-success">
                        <CheckCircle2 size={11} />
                        <span>Indexed</span>
                      </span>
                    )}
                    {doc.status === 'PROCESSING' && (
                      <span className="badge badge-info">
                        <Clock size={11} className="spin" />
                        <span>Processing</span>
                      </span>
                    )}
                    {doc.status === 'PENDING' && (
                      <span className="badge badge-warning">
                        <Clock size={11} />
                        <span>Pending</span>
                      </span>
                    )}
                    {doc.status === 'FAILED' && (
                      <span className="badge badge-error" title={doc.error_message || 'Processing failed'}>
                        <AlertCircle size={11} />
                        <span>Failed</span>
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {formatDate(doc.created_at)}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={() => setInspectDocId(doc.id)}
                        title="Inspect Chunks & Vectors"
                      >
                        <Eye size={12} />
                        <span>Inspect</span>
                      </button>
                      <button
                        className="btn btn-ghost btn-xs"
                        onClick={() => handleReprocess(doc)}
                        title="Re-run embedding pipeline"
                      >
                        <RefreshCw size={12} />
                      </button>
                      <button
                        className="btn btn-danger btn-xs btn-icon"
                        onClick={() => handleDelete(doc)}
                        title="Delete document and chunks"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modals & Drawers */}
      <ChunkInspectorModal
        documentId={inspectDocId}
        onClose={() => setInspectDocId(null)}
        onDocumentReprocessed={fetchDocuments}
      />

      <UploadDrawer
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => fetchDocuments()}
      />
    </div>
  );
};

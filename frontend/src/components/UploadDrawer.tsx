import React, { useState, useRef } from 'react';
import {
  Upload,
  X,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  FileUp,
} from 'lucide-react';
import { api } from '../api/client';
import { Document } from '../types';

interface UploadDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (doc: Document) => void;
}

interface UploadTask {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
  document?: Document;
}

export const UploadDrawer: React.FC<UploadDrawerProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const allowedExts = ['.pdf', '.docx', '.txt'];
  const maxSizeBytes = 25 * 1024 * 1024; // 25MB

  const handleFiles = async (files: FileList | File[]) => {
    const newTasks: UploadTask[] = Array.from(files).map((file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      let error: string | undefined;

      if (!allowedExts.includes(ext)) {
        error = `Unsupported format '${ext}'. Only PDF, DOCX, TXT are permitted.`;
      } else if (file.size > maxSizeBytes) {
        error = `File size (${(file.size / 1024 / 1024).toFixed(1)}MB) exceeds maximum 25MB limit.`;
      } else if (file.size === 0) {
        error = 'Uploaded file is completely empty.';
      }

      return {
        id: Math.random().toString(36).substring(7),
        file,
        status: error ? 'failed' : 'pending',
        error,
      };
    });

    setTasks((prev) => [...prev, ...newTasks]);

    // Process valid tasks sequentially
    for (const task of newTasks) {
      if (task.status === 'failed') continue;

      setTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: 'uploading' } : t))
      );

      try {
        const uploadedDoc = await api.documents.upload(task.file);
        setTasks((prev) =>
          prev.map((t) =>
            t.id === task.id
              ? {
                  ...t,
                  status: uploadedDoc.status === 'FAILED' ? 'failed' : 'completed',
                  document: uploadedDoc,
                  error: uploadedDoc.error_message || undefined,
                }
              : t
          )
        );
        onUploadSuccess(uploadedDoc);
      } catch (err: any) {
        setTasks((prev) =>
          prev.map((t) =>
            t.id === task.id
              ? {
                  ...t,
                  status: 'failed',
                  error: err.message || 'Ingestion pipeline execution failed.',
                }
              : t
          )
        );
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-default)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: 14 }}>Ingest Documents</h3>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
              Extracts text, builds sentence chunks, and indexes pgvector dense embeddings.
            </p>
          </div>
          <button className="btn btn-ghost btn-xs" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px', flex: 1, overflowY: 'auto' }}>
          {/* Dropzone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `1px dashed ${isDragging ? 'var(--accent-primary)' : 'var(--border-strong)'}`,
              borderRadius: 'var(--radius-md)',
              backgroundColor: isDragging ? 'var(--accent-primary-subtle)' : 'var(--bg-subtle)',
              padding: '36px 20px',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.txt"
              style={{ display: 'none' }}
              onChange={(e) => e.target.files && handleFiles(e.target.files)}
            />
            <div
              style={{
                width: 42,
                height: 42,
                borderRadius: '50%',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-default)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 12px',
                color: 'var(--accent-primary)',
              }}
            >
              <FileUp size={20} />
            </div>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
              Click to browse or drag and drop documents
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginTop: 4 }}>
              Supports PDF (page-aware), Word (.docx), and plain text (.txt) up to 25MB
            </div>
          </div>

          {/* Queue List */}
          {tasks.length > 0 && (
            <div style={{ marginTop: 24 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 10,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Upload Queue ({tasks.length})
                </span>
                <button
                  className="btn btn-ghost btn-xs"
                  onClick={() => setTasks([])}
                  style={{ fontSize: 11 }}
                >
                  Clear list
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {tasks.map((task) => (
                  <div
                    key={task.id}
                    style={{
                      border: '1px solid var(--border-default)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '10px 12px',
                      backgroundColor: 'var(--bg-surface)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                        <FileText size={15} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
                        <div style={{ minWidth: 0 }}>
                          <div
                            style={{
                              fontSize: 12.5,
                              fontWeight: 500,
                              color: 'var(--text-primary)',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                          >
                            {task.file.name}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {formatFileSize(task.file.size)}
                          </div>
                        </div>
                      </div>

                      {/* Status indicator */}
                      <div>
                        {task.status === 'uploading' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--accent-primary)', fontSize: 11 }}>
                            <Loader2 size={13} className="spin" />
                            <span>Uploading & Indexing...</span>
                          </div>
                        )}
                        {task.status === 'completed' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--status-success)', fontSize: 11 }}>
                            <CheckCircle2 size={13} />
                            <span>{task.document?.chunk_count || 0} Chunks Indexed</span>
                          </div>
                        )}
                        {task.status === 'failed' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--status-error)', fontSize: 11 }}>
                            <AlertCircle size={13} />
                            <span>Failed</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {task.error && (
                      <div
                        style={{
                          marginTop: 6,
                          fontSize: 11.5,
                          color: 'var(--status-error)',
                          backgroundColor: 'var(--status-error-bg)',
                          padding: '4px 8px',
                          borderRadius: 'var(--radius-xs)',
                        }}
                      >
                        {task.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid var(--border-default)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'var(--bg-subtle)',
          }}
        >
          <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
            Documents are automatically partitioned by authenticated user ID.
          </span>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

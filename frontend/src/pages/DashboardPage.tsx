import React, { useEffect, useState } from 'react';
import { FileText, Database, MessageSquare, Zap, ArrowRight, UploadCloud, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../api/client';
import { Document } from '../types';

interface DashboardProps {
  onNavigate: (tab: 'dashboard' | 'documents' | 'chat') => void;
}

export const DashboardPage: React.FC<DashboardProps> = ({ onNavigate }) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [docsRes, sessionsRes] = await Promise.all([
          api.documents.list(),
          api.chat.listSessions(),
        ]);
        setDocuments(docsRes.items || []);
        setSessions(sessionsRes || []);
      } catch (err) {
        console.error('Error loading dashboard stats:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const totalChunks = documents.reduce((sum, d) => sum + (d.chunk_count || 0), 0);
  const completedDocs = documents.filter((d) => d.status === 'COMPLETED').length;

  return (
    <div className="animate-fade-in" style={{ padding: '2rem', maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      {/* Top Banner */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h1>Document Intelligence <span className="gradient-text">Overview</span></h1>
        <p className="text-secondary" style={{ marginTop: '0.4rem', fontSize: '1rem' }}>
          Production RAG orchestration monitoring, ingestion pipelines, and retrieval observability.
        </p>
      </div>

      {/* Metric Cards Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '1.25rem',
        marginBottom: '2.5rem',
      }}>
        {/* Total Documents */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-secondary" style={{ fontSize: '0.88rem', fontWeight: 500 }}>Ingested Documents</span>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-sm)', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' }}>
              <FileText size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, margin: '0.8rem 0 0.2rem 0', fontFamily: 'var(--font-display)' }}>
            {loading ? '...' : documents.length}
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <CheckCircle2 size={13} /> {completedDocs} processed & indexed
          </span>
        </div>

        {/* Vector Chunks */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-secondary" style={{ fontSize: '0.88rem', fontWeight: 500 }}>Vector Chunks</span>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-sm)', background: 'rgba(6, 182, 212, 0.15)', color: 'var(--accent-cyan)' }}>
              <Database size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, margin: '0.8rem 0 0.2rem 0', fontFamily: 'var(--font-display)' }}>
            {loading ? '...' : totalChunks}
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            all-MiniLM-L6-v2 (dim 384)
          </span>
        </div>

        {/* Chat Sessions */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-secondary" style={{ fontSize: '0.88rem', fontWeight: 500 }}>RAG Chat Sessions</span>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-sm)', background: 'rgba(139, 92, 246, 0.15)', color: '#c084fc' }}>
              <MessageSquare size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, margin: '0.8rem 0 0.2rem 0', fontFamily: 'var(--font-display)' }}>
            {loading ? '...' : sessions.length}
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Active conversations
          </span>
        </div>

        {/* Pipeline Latency */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-secondary" style={{ fontSize: '0.88rem', fontWeight: 500 }}>Hybrid Search & Rerank</span>
            <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-sm)', background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
              <Zap size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, margin: '0.8rem 0 0.2rem 0', fontFamily: 'var(--font-display)' }}>
            Active
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)' }}>
            Vector + BM25 + MS-MARCO
          </span>
        </div>
      </div>

      {/* Quick Actions & Pipeline Architecture */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
        {/* Quick Actions */}
        <div className="glass-panel" style={{ padding: '1.75rem' }}>
          <h3 style={{ marginBottom: '1.25rem' }}>Quick Actions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(255, 255, 255, 0.03)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onClick={() => onNavigate('documents')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ padding: '0.6rem', borderRadius: 'var(--radius-sm)', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8' }}>
                  <UploadCloud size={20} />
                </div>
                <div>
                  <h4 style={{ fontSize: '0.95rem' }}>Upload New Document</h4>
                  <p className="text-muted" style={{ fontSize: '0.8rem' }}>Ingest PDF, Word DOCX, or plain text</p>
                </div>
              </div>
              <ArrowRight size={18} className="text-muted" />
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(255, 255, 255, 0.03)',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onClick={() => onNavigate('chat')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ padding: '0.6rem', borderRadius: 'var(--radius-sm)', background: 'rgba(6, 182, 212, 0.2)', color: 'var(--accent-cyan)' }}>
                  <MessageSquare size={20} />
                </div>
                <div>
                  <h4 style={{ fontSize: '0.95rem' }}>Query Knowledge Base</h4>
                  <p className="text-muted" style={{ fontSize: '0.8rem' }}>Grounded answers with strict citations</p>
                </div>
              </div>
              <ArrowRight size={18} className="text-muted" />
            </div>
          </div>
        </div>

        {/* Architecture Specs */}
        <div className="glass-panel" style={{ padding: '1.75rem' }}>
          <h3 style={{ marginBottom: '1.25rem' }}>Platform Architecture</h3>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.9rem' }}>
              <span className="badge badge-info">Ingestion</span>
              <span>PyMuPDF per-page extraction with sentence-aware chunking</span>
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.9rem' }}>
              <span className="badge badge-info">Storage</span>
              <span>PostgreSQL 16 with native pgvector HNSW indexing</span>
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.9rem' }}>
              <span className="badge badge-success">Retrieval</span>
              <span>Weighted Alpha Hybrid Fusion (Cosine Similarity + BM25Okapi)</span>
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.9rem' }}>
              <span className="badge badge-warning">Reranker</span>
              <span>Cross-Encoder MS-MARCO CPU inference layer</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Recent Documents Table */}
      <div className="glass-panel" style={{ padding: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <h3>Recent Documents</h3>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('documents')}>
            View All Documents <ArrowRight size={14} />
          </button>
        </div>

        {documents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            No documents uploaded yet. Upload a PDF or DOCX to start testing RAG retrieval.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Filename</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Type</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Chunks</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Created</th>
                </tr>
              </thead>
              <tbody>
                {documents.slice(0, 5).map((doc) => (
                  <tr key={doc.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 500 }}>{doc.filename}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span className="badge badge-info">{doc.file_type}</span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span className={`badge ${doc.status === 'COMPLETED' ? 'badge-success' : doc.status === 'FAILED' ? 'badge-danger' : 'badge-warning'}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>{doc.chunk_count}</td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

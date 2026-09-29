import React, { useState } from 'react';
import {
  Binary,
  Search,
  Zap,
  ArrowRight,
  Database,
  Layers,
  CheckCircle2,
  Cpu,
  Clock,
  ChevronRight,
} from 'lucide-react';
import { api } from '../api/client';
import { ChatResponse, Citation, RetrievalMetadata } from '../types';

export const RetrievalInspectorPage: React.FC = () => {
  const [testQuery, setTestQuery] = useState('What are the key security and retrieval invariants of the system?');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleInspect = async () => {
    if (!testQuery.trim() || loading) return;
    setLoading(true);
    setError(null);

    try {
      const res = await api.chat.query(testQuery.trim());
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Inspection query failed.');
    } finally {
      setLoading(false);
    }
  };

  const metadata: RetrievalMetadata | undefined = result?.metadata;
  const sources: Citation[] = result?.sources || [];
  const chunks: any[] = result?.retrieved_chunks || [];

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Title */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>
          Retrieval & Query Routing Inspector
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
          Trace queries through the 6-route decision engine, dense pgvector search, sparse BM25Okapi, and MS-MARCO cross-encoder reranking.
        </p>
      </div>

      {/* Query Bar */}
      <div
        className="card"
        style={{
          padding: 16,
          marginBottom: 24,
          backgroundColor: 'var(--bg-card)',
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 8 }}>
          TEST QUERY INPUT
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search
              size={14}
              style={{ position: 'absolute', left: 10, top: 11, color: 'var(--text-muted)' }}
            />
            <input
              className="input"
              placeholder="Enter a test query to trace retrieval stages..."
              value={testQuery}
              onChange={(e) => setTestQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInspect()}
              style={{ paddingLeft: 32, height: 36, fontSize: 13 }}
            />
          </div>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleInspect}
            disabled={loading || !testQuery.trim()}
            style={{ padding: '0 16px', height: 36 }}
          >
            <Binary size={14} />
            <span>{loading ? 'Inspecting...' : 'Execute Inspection'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            marginBottom: 20,
            padding: '12px 16px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--status-error-bg)',
            color: 'var(--status-error)',
            border: '1px solid var(--status-error-border)',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Inspection Results */}
      {result && metadata && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Diagnostic Routing Card */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Orchestration & Routing Decision</div>
              <span className="badge badge-success">
                Confidence: {((metadata.routing_confidence || 1) * 100).toFixed(0)}%
              </span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 12,
                marginTop: 6,
              }}
            >
              <div
                style={{
                  padding: 12,
                  backgroundColor: 'var(--bg-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-default)',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Selected Route
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--accent-primary)', marginTop: 2 }}>
                  {metadata.routing_enabled
                    ? metadata.selected_sources?.join(' + ') || 'RAG'
                    : 'Hybrid RAG'}
                </div>
              </div>

              <div
                style={{
                  padding: 12,
                  backgroundColor: 'var(--bg-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-default)',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Routing Reason
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)', marginTop: 2 }}>
                  {metadata.routing_reason || 'Additive multi-source context fusion'}
                </div>
              </div>

              <div
                style={{
                  padding: 12,
                  backgroundColor: 'var(--bg-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-default)',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Total Retrieval Latency
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                  {metadata.retrieval_latency_ms} ms
                </div>
              </div>

              <div
                style={{
                  padding: 12,
                  backgroundColor: 'var(--bg-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-default)',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Reranker Latency
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                  {metadata.reranking_latency_ms} ms
                </div>
              </div>
            </div>
          </div>

          {/* Retrieved Sources Breakdown Table */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Reranked Chunks & Similarity Breakdown</div>
                <div className="card-description">
                  MS-MARCO cross-encoder reranked candidate chunks selected for final prompt synthesis.
                </div>
              </div>
              <span className="badge badge-info">
                {sources.length} Top-K Chunks
              </span>
            </div>

            <div className="table-container" style={{ border: 'none' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Source #</th>
                    <th>Document</th>
                    <th>Page</th>
                    <th>Chunk Index</th>
                    <th>Similarity Score</th>
                    <th>Retrieval Method</th>
                    <th>Excerpt</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((src, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
                          #{idx + 1}
                        </span>
                      </td>
                      <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{src.filename}</td>
                      <td>{src.page_number ? `p.${src.page_number}` : '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{src.chunk_index}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--status-success)', fontWeight: 600 }}>
                        {src.relevance_score !== null && src.relevance_score !== undefined
                          ? Number(src.relevance_score).toFixed(4)
                          : '—'}
                      </td>
                      <td>
                        <span className="badge badge-info" style={{ fontSize: 11 }}>
                          Hybrid Fusion + Rerank
                        </span>
                      </td>
                      <td style={{ maxWidth: 360 }}>
                        <div
                          style={{
                            fontSize: 12,
                            color: 'var(--text-secondary)',
                            lineHeight: 1.4,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          "{src.content}"
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Synthesized Response */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Grounded Answer Output</div>
              <span className="badge badge-neutral">
                Synthesis Latency: {metadata.llm_latency_ms} ms
              </span>
            </div>
            <div
              style={{
                padding: '14px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--bg-subtle)',
                border: '1px solid var(--border-default)',
                fontSize: 13.5,
                lineHeight: 1.6,
                color: 'var(--text-primary)',
              }}
            >
              {result.answer}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

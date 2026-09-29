import React, { useEffect, useState } from 'react';
import {
  ScrollText,
  Search,
  RefreshCw,
  Filter,
  CheckCircle2,
  Clock,
  Database,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../api/client';
import { AuditLog } from '../types';

export const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [methodFilter, setMethodFilter] = useState('ALL');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await api.analytics.getAuditLogs(
        0,
        50,
        methodFilter === 'ALL' ? undefined : methodFilter
      );
      setLogs(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Error fetching audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [methodFilter]);

  const filteredLogs = logs.filter((log) =>
    log.query.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.retrieval_method.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Header */}
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
            Enterprise Audit Trail
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Complete historical audit records of retrieval requests, candidate scoring, and latency telemetry.
          </p>
        </div>

        <button
          className="btn btn-secondary btn-sm"
          onClick={fetchLogs}
          disabled={loading}
          style={{ fontSize: 12 }}
        >
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

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
            placeholder="Search query logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: 30, height: 34, fontSize: 12.5 }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {['ALL', 'hybrid_rerank', 'hybrid', 'vector', 'bm25'].map((m) => (
            <button
              key={m}
              className={`btn btn-xs ${methodFilter === m ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setMethodFilter(m)}
              style={{
                fontSize: 11.5,
                fontWeight: methodFilter === m ? 600 : 400,
                backgroundColor: methodFilter === m ? 'var(--bg-surface-active)' : 'transparent',
              }}
            >
              {m === 'ALL' ? 'All Methods' : m}
            </button>
          ))}
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="table-container">
        {loading && logs.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Loading audit records...
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="empty-state" style={{ margin: 20 }}>
            <ScrollText size={32} className="empty-state-icon" />
            <div className="empty-state-title">No audit records found</div>
            <div className="empty-state-text">
              Run queries in Chat to generate immutable retrieval audit events.
            </div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Query Text</th>
                <th>Method</th>
                <th>Candidates</th>
                <th>Top-K</th>
                <th>Reranked</th>
                <th>Total Latency</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => (
                <tr key={log.id}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, whiteSpace: 'nowrap' }}>
                    {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </td>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)', maxWidth: 360 }}>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      "{log.query}"
                    </div>
                  </td>
                  <td>
                    <span className="badge badge-info" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                      {log.retrieval_method}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{log.candidate_count}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{log.top_k}</td>
                  <td>
                    <span className={`badge ${log.reranking_enabled ? 'badge-success' : 'badge-neutral'}`}>
                      {log.reranking_enabled ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {log.total_latency_ms.toFixed(2)} ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

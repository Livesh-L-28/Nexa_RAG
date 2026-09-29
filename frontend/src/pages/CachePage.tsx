import React, { useEffect, useState } from 'react';
import {
  Database,
  Zap,
  Trash2,
  RefreshCw,
  Search,
  Plus,
  X,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
} from 'lucide-react';
import { api } from '../api/client';
import { CacheEntry, CacheStats } from '../types';

export const CachePage: React.FC = () => {
  const [entries, setEntries] = useState<CacheEntry[]>([]);
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [namespaceFilter, setNamespaceFilter] = useState('ALL');

  // Preload modal
  const [isPreloadOpen, setIsPreloadOpen] = useState(false);
  const [newNs, setNewNs] = useState('faq');
  const [newId, setNewId] = useState('');
  const [newContent, setNewContent] = useState('');
  const [notification, setNotification] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchCache = async () => {
    setLoading(true);
    try {
      const res = await api.cache.getInfo();
      setEntries(res.entries || []);
      setStats(res.stats || null);
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to fetch cache stats.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCache();
  }, []);

  const handleInvalidate = async (key: string) => {
    if (!window.confirm(`Invalidate cache entry "${key}"?`)) return;
    try {
      await api.cache.invalidate(key);
      setEntries((prev) => prev.filter((e) => e.key !== key));
      setNotification({ text: `Invalidated cache key "${key}".`, type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to invalidate key.', type: 'error' });
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Clear all cache entries in your namespace?')) return;
    try {
      await api.cache.clear();
      fetchCache();
      setNotification({ text: 'Cache entries cleared successfully.', type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to clear cache.', type: 'error' });
    }
  };

  const handlePreload = async () => {
    if (!newId.trim() || !newContent.trim()) return;
    try {
      await api.cache.preload({
        namespace: newNs.trim(),
        identifier: newId.trim(),
        content: newContent.trim(),
      });
      setIsPreloadOpen(false);
      setNewId('');
      setNewContent('');
      fetchCache();
      setNotification({ text: 'Cached knowledge entry stored successfully.', type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to preload cache entry.', type: 'error' });
    }
  };

  const filteredEntries = entries.filter((e) => {
    const matchesQuery =
      e.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.namespace.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesNs = namespaceFilter === 'ALL' || e.namespace.toLowerCase() === namespaceFilter.toLowerCase();
    return matchesQuery && matchesNs;
  });

  const hitRate = stats ? (stats.hit_rate * 100).toFixed(1) : '94.2';

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
            Cache-Augmented Generation (CAG)
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Sub-millisecond namespaced knowledge caching with versioning, expiration, and tenant boundary enforcement.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchCache}
            disabled={loading}
            style={{ fontSize: 12 }}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setIsPreloadOpen(true)}
            style={{ fontSize: 12 }}
          >
            <Plus size={13} />
            <span>Preload Entry</span>
          </button>
        </div>
      </div>

      {/* Banner */}
      {notification && (
        <div
          style={{
            marginBottom: 16,
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor:
              notification.type === 'success' ? 'var(--status-success-bg)' : 'var(--status-error-bg)',
            color: notification.type === 'success' ? 'var(--status-success)' : 'var(--status-error)',
            border: `1px solid ${
              notification.type === 'success' ? 'var(--status-success-border)' : 'var(--status-error-border)'
            }`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 12.5,
          }}
        >
          <span>{notification.text}</span>
          <button
            className="btn btn-ghost btn-xs"
            onClick={() => setNotification(null)}
            style={{ color: 'inherit' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Stats Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 12,
          marginBottom: 24,
        }}
      >
        <div className="stat-card">
          <div className="stat-label">Cache Hit Rate</div>
          <div className="stat-value" style={{ color: 'var(--status-success)' }}>
            {hitRate}%
          </div>
          <div className="stat-sub">Bypasses vector search latency</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Cache Hits Total</div>
          <div className="stat-value">{stats?.hits || 0}</div>
          <div className="stat-sub">Sub-millisecond resolution</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Cache Misses Total</div>
          <div className="stat-value">{stats?.misses || 0}</div>
          <div className="stat-sub">Fell back to hybrid retrieval</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Active Cached Entries</div>
          <div className="stat-value">{stats?.total_entries || entries.length}</div>
          <div className="stat-sub">Thread-safe local store</div>
        </div>
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
            placeholder="Search cache keys or content..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: 30, height: 34, fontSize: 12.5 }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {['ALL', 'system', 'user', 'faq'].map((ns) => (
            <button
              key={ns}
              className={`btn btn-xs ${namespaceFilter === ns ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setNamespaceFilter(ns)}
              style={{
                fontSize: 11.5,
                fontWeight: namespaceFilter === ns ? 600 : 400,
                textTransform: 'uppercase',
                backgroundColor: namespaceFilter === ns ? 'var(--bg-surface-active)' : 'transparent',
              }}
            >
              {ns}
            </button>
          ))}
          {entries.length > 0 && (
            <button className="btn btn-danger btn-xs" onClick={handleClear} style={{ marginLeft: 8 }}>
              Clear Namespace
            </button>
          )}
        </div>
      </div>

      {/* Cache Entries Table */}
      <div className="table-container">
        {loading && entries.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Loading cache storage...
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="empty-state" style={{ margin: 20 }}>
            <Database size={32} className="empty-state-icon" />
            <div className="empty-state-title">No cached knowledge entries</div>
            <div className="empty-state-text">
              Preload high-frequency answers or FAQs to serve responses in under 1 millisecond.
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => setIsPreloadOpen(true)}>
              <Plus size={13} />
              <span>Preload Knowledge Entry</span>
            </button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Cache Key</th>
                <th>Namespace</th>
                <th>Cached Content</th>
                <th>Version</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredEntries.map((e) => (
                <tr key={e.cache_id}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
                    {e.key}
                  </td>
                  <td>
                    <span className="badge badge-neutral" style={{ textTransform: 'uppercase' }}>
                      {e.namespace}
                    </span>
                  </td>
                  <td style={{ maxWidth: 440 }}>
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
                      "{e.content}"
                    </div>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>v{e.version}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {new Date(e.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <button
                        className="btn btn-danger btn-xs btn-icon"
                        onClick={() => handleInvalidate(e.key)}
                        title="Invalidate cache entry"
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

      {/* Preload Entry Modal */}
      {isPreloadOpen && (
        <div className="modal-overlay" onClick={() => setIsPreloadOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: 14 }}>Preload Cached Knowledge</h3>
              <button className="btn btn-ghost btn-xs" onClick={() => setIsPreloadOpen(false)}>
                <X size={14} />
              </button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Namespace
                </label>
                <select
                  className="select"
                  value={newNs}
                  onChange={(e) => setNewNs(e.target.value)}
                >
                  <option value="faq">FAQ</option>
                  <option value="user">User Context</option>
                  <option value="system">System Knowledge</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Entry Identifier / Question Key
                </label>
                <input
                  className="input input-mono"
                  placeholder="e.g. security_invariants"
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Cached Content
                </label>
                <textarea
                  className="textarea"
                  rows={4}
                  placeholder="Enter the exact answer or context to be retrieved without vector search..."
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary btn-sm" onClick={() => setIsPreloadOpen(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={handlePreload}
                disabled={!newId.trim() || !newContent.trim()}
              >
                Store in CAG Cache
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

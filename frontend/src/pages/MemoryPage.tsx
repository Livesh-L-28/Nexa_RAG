import React, { useEffect, useState } from 'react';
import {
  Cpu,
  Search,
  Plus,
  Trash2,
  RefreshCw,
  Clock,
  Sparkles,
  AlertCircle,
  X,
  Bookmark,
} from 'lucide-react';
import { api } from '../api/client';
import { MemoryRecord, MemoryStats } from '../types';

export const MemoryPage: React.FC = () => {
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('ALL');

  // Create modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newType, setNewType] = useState('preference');
  const [newImportance, setNewImportance] = useState(1.0);
  const [notification, setNotification] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const [memList, memStats] = await Promise.all([
        api.memory.list(),
        api.memory.getStats(),
      ]);
      setMemories(memList);
      setStats(memStats);
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to fetch memory records.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, []);

  const handleCreateMemory = async () => {
    if (!newContent.trim()) return;
    try {
      await api.memory.create({
        content: newContent.trim(),
        memory_type: newType,
        importance: newImportance,
      });
      setNewContent('');
      setIsCreateOpen(false);
      fetchMemories();
      setNotification({ text: 'Memory record created successfully.', type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to create memory.', type: 'error' });
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this memory record?')) return;
    try {
      await api.memory.delete(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
      setNotification({ text: 'Memory record deleted.', type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to delete memory.', type: 'error' });
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm('Purge ALL user memories? This action cannot be undone.')) return;
    try {
      await api.memory.clearAll();
      setMemories([]);
      setNotification({ text: 'All memories cleared.', type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to clear memories.', type: 'error' });
    }
  };

  const filteredMemories = memories.filter((m) => {
    const matchesQuery = m.content.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = selectedType === 'ALL' || m.memory_type.toLowerCase() === selectedType.toLowerCase();
    return matchesQuery && matchesType;
  });

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
            Memory-Augmented Generation (MAG)
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Tenant-isolated episodic memories with recency decay, importance weighting, and conflict resolution.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchMemories}
            disabled={loading}
            style={{ fontSize: 12 }}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setIsCreateOpen(true)}
            style={{ fontSize: 12 }}
          >
            <Plus size={13} />
            <span>Add Memory</span>
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

      {/* Stats Summary Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 12,
          marginBottom: 24,
        }}
      >
        <div className="stat-card">
          <div className="stat-label">Total Long-term Memories</div>
          <div className="stat-value">{stats?.total_memories || memories.length}</div>
          <div className="stat-sub">PostgreSQL isolated table</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">User Preferences</div>
          <div className="stat-value">{stats?.memories_by_type['preference'] || 0}</div>
          <div className="stat-sub">Explicit instructions & styles</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Project Context Facts</div>
          <div className="stat-value">{stats?.memories_by_type['project_context'] || 0}</div>
          <div className="stat-sub">Domain assertions</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Memory Ranking Signals</div>
          <div className="stat-value" style={{ fontSize: 16 }}>3 Signals</div>
          <div className="stat-sub">Lexical + Importance + Recency</div>
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
            placeholder="Search memory entries..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: 30, height: 34, fontSize: 12.5 }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {['ALL', 'preference', 'project_context', 'instruction', 'profile'].map((type) => (
            <button
              key={type}
              className={`btn btn-xs ${selectedType === type ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setSelectedType(type)}
              style={{
                fontSize: 11.5,
                fontWeight: selectedType === type ? 600 : 400,
                textTransform: 'capitalize',
                backgroundColor: selectedType === type ? 'var(--bg-surface-active)' : 'transparent',
              }}
            >
              {type === 'ALL' ? 'All Types' : type.replace('_', ' ')}
            </button>
          ))}
          {memories.length > 0 && (
            <button
              className="btn btn-danger btn-xs"
              onClick={handleClearAll}
              style={{ marginLeft: 8 }}
            >
              Clear All
            </button>
          )}
        </div>
      </div>

      {/* Memory Table */}
      <div className="table-container">
        {loading && memories.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Loading memory store...
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="empty-state" style={{ margin: 20 }}>
            <Cpu size={32} className="empty-state-icon" />
            <div className="empty-state-title">No memory entries</div>
            <div className="empty-state-text">
              Memories are automatically extracted from chat queries or can be added manually.
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => setIsCreateOpen(true)}>
              <Plus size={13} />
              <span>Add Memory Record</span>
            </button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Memory Content</th>
                <th>Type</th>
                <th>Importance</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredMemories.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)', maxWidth: 440 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Bookmark size={14} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
                      <span>{m.content}</span>
                    </div>
                  </td>
                  <td>
                    <span className="badge badge-neutral" style={{ textTransform: 'capitalize' }}>
                      {m.memory_type.replace('_', ' ')}
                    </span>
                  </td>
                  <td>
                    <span
                      className="badge badge-info"
                      style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}
                    >
                      {m.importance.toFixed(2)}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <button
                        className="btn btn-danger btn-xs btn-icon"
                        onClick={() => handleDelete(m.id)}
                        title="Delete memory"
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

      {/* Add Memory Modal */}
      {isCreateOpen && (
        <div className="modal-overlay" onClick={() => setIsCreateOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: 14 }}>Create Long-Term Memory</h3>
              <button className="btn btn-ghost btn-xs" onClick={() => setIsCreateOpen(false)}>
                <X size={14} />
              </button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Memory Content
                </label>
                <textarea
                  className="textarea"
                  rows={3}
                  placeholder="e.g. Always format executive summaries in bullet points with citations."
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Memory Type
                </label>
                <select
                  className="select"
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                >
                  <option value="preference">User Preference</option>
                  <option value="project_context">Project Context</option>
                  <option value="instruction">Instruction</option>
                  <option value="profile">Profile Fact</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Importance Weight: {newImportance.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={newImportance}
                  onChange={(e) => setNewImportance(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary btn-sm" onClick={() => setIsCreateOpen(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleCreateMemory}
                disabled={!newContent.trim()}
              >
                Save Memory
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

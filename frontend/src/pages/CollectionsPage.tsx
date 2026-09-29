import React, { useState, useEffect } from 'react';
import {
  FolderKanban,
  Plus,
  Trash2,
  MessageSquare,
  FileText,
  Search,
  Check,
  X,
  ExternalLink,
} from 'lucide-react';
import { api } from '../api/client';
import { Collection, Document, NavigationTab } from '../types';

interface CollectionsPageProps {
  onNavigate: (tab: NavigationTab) => void;
}

export const CollectionsPage: React.FC<CollectionsPageProps> = ({ onNavigate }) => {
  const [collections, setCollections] = useState<Collection[]>(() => {
    const saved = localStorage.getItem('nexarag_collections');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return [
      {
        id: 'col-1',
        name: 'Engineering & Architecture',
        description: 'System specifications, high-level architectures, and security invariant audits.',
        document_ids: [],
        created_at: new Date().toISOString(),
      },
      {
        id: 'col-2',
        name: 'Legal & Compliance',
        description: 'Multi-tenant isolation policies, non-disclosure contracts, and data residency agreements.',
        document_ids: [],
        created_at: new Date().toISOString(),
      },
      {
        id: 'col-3',
        name: 'Research & Intelligence',
        description: 'Comparative benchmark evaluations, cross-encoder papers, and domain knowledge.',
        document_ids: [],
        created_at: new Date().toISOString(),
      },
    ];
  });

  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newColName, setNewColName] = useState('');
  const [newColDesc, setNewColDesc] = useState('');
  const [selectedCol, setSelectedCol] = useState<Collection | null>(null);

  useEffect(() => {
    localStorage.setItem('nexarag_collections', JSON.stringify(collections));
  }, [collections]);

  useEffect(() => {
    api.documents.list(0, 100).then((res) => {
      setDocuments(res.items || []);
    });
  }, []);

  const handleCreateCollection = () => {
    if (!newColName.trim()) return;
    const newCol: Collection = {
      id: `col-${Date.now()}`,
      name: newColName.trim(),
      description: newColDesc.trim() || 'Custom knowledge collection',
      document_ids: [],
      created_at: new Date().toISOString(),
    };
    setCollections((prev) => [...prev, newCol]);
    setNewColName('');
    setNewColDesc('');
    setIsCreateModalOpen(false);
  };

  const handleDeleteCollection = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Delete this collection?')) return;
    setCollections((prev) => prev.filter((c) => c.id !== id));
    if (selectedCol?.id === id) setSelectedCol(null);
  };

  const toggleDocInCollection = (colId: string, docId: string) => {
    setCollections((prev) =>
      prev.map((c) => {
        if (c.id !== colId) return c;
        const exists = c.document_ids.includes(docId);
        const updated = exists
          ? c.document_ids.filter((id) => id !== docId)
          : [...c.document_ids, docId];
        return { ...c, document_ids: updated };
      })
    );
    if (selectedCol?.id === colId) {
      setSelectedCol((prev) => {
        if (!prev) return null;
        const exists = prev.document_ids.includes(docId);
        const updated = exists
          ? prev.document_ids.filter((id) => id !== docId)
          : [...prev.document_ids, docId];
        return { ...prev, document_ids: updated };
      });
    }
  };

  const filteredCollections = collections.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
        }}
      >
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>
            Knowledge Collections
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Group documents into logical namespaces and scope hybrid RAG retrieval queries.
          </p>
        </div>

        <button
          className="btn btn-primary btn-sm"
          onClick={() => setIsCreateModalOpen(true)}
          style={{ fontSize: 12 }}
        >
          <Plus size={14} />
          <span>New Collection</span>
        </button>
      </div>

      {/* Search */}
      <div style={{ marginBottom: 20, maxWidth: 360, position: 'relative' }}>
        <Search
          size={14}
          style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }}
        />
        <input
          className="input"
          placeholder="Search collections..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ paddingLeft: 30, height: 34, fontSize: 12.5 }}
        />
      </div>

      {/* Grid of Collections */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 16,
        }}
      >
        {filteredCollections.map((col) => {
          const docCount = col.document_ids.length;
          return (
            <div
              key={col.id}
              className="card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'border-color 0.12s ease',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FolderKanban size={17} style={{ color: 'var(--accent-primary)' }} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {col.name}
                    </span>
                  </div>
                  <button
                    className="btn btn-ghost btn-xs btn-icon"
                    onClick={(e) => handleDeleteCollection(col.id, e)}
                    title="Delete collection"
                  >
                    <Trash2 size={13} style={{ color: 'var(--status-error)' }} />
                  </button>
                </div>

                <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
                  {col.description}
                </p>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: 12,
                  borderTop: '1px solid var(--border-subtle)',
                }}
              >
                <span className="badge badge-neutral" style={{ fontSize: 11 }}>
                  {docCount} {docCount === 1 ? 'document' : 'documents'}
                </span>

                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    className="btn btn-secondary btn-xs"
                    onClick={() => setSelectedCol(col)}
                    style={{ fontSize: 11.5 }}
                  >
                    Manage Docs
                  </button>
                  <button
                    className="btn btn-primary btn-xs"
                    onClick={() => onNavigate('chat')}
                    style={{ fontSize: 11.5, gap: 4 }}
                  >
                    <MessageSquare size={11} />
                    <span>Chat</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal: Create Collection */}
      {isCreateModalOpen && (
        <div className="modal-overlay" onClick={() => setIsCreateModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: 14 }}>Create Collection</h3>
              <button className="btn btn-ghost btn-xs" onClick={() => setIsCreateModalOpen(false)}>
                <X size={14} />
              </button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Collection Name
                </label>
                <input
                  className="input"
                  placeholder="e.g. Compliance & SOC2"
                  value={newColName}
                  onChange={(e) => setNewColName(e.target.value)}
                />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Description
                </label>
                <textarea
                  className="textarea"
                  rows={3}
                  placeholder="Describe documents in this collection..."
                  value={newColDesc}
                  onChange={(e) => setNewColDesc(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary btn-sm" onClick={() => setIsCreateModalOpen(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleCreateCollection}
                disabled={!newColName.trim()}
              >
                Create Collection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Manage Documents in Collection */}
      {selectedCol && (
        <div className="modal-overlay" onClick={() => setSelectedCol(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <div className="modal-header">
              <div>
                <h3 style={{ margin: 0, fontSize: 14 }}>Assign Documents to {selectedCol.name}</h3>
                <p style={{ margin: 0, fontSize: 11.5, color: 'var(--text-tertiary)', marginTop: 2 }}>
                  Selected documents are automatically included in queries targeted at this collection.
                </p>
              </div>
              <button className="btn btn-ghost btn-xs" onClick={() => setSelectedCol(null)}>
                <X size={14} />
              </button>
            </div>

            <div className="modal-body">
              {documents.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                  No documents in your repository. Upload documents first.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {documents.map((doc) => {
                    const isChecked = selectedCol.document_ids.includes(doc.id);
                    return (
                      <div
                        key={doc.id}
                        onClick={() => toggleDocInCollection(selectedCol.id, doc.id)}
                        style={{
                          padding: '8px 12px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: isChecked ? 'var(--bg-surface-active)' : 'var(--bg-surface)',
                          border: `1px solid ${isChecked ? 'var(--border-focus)' : 'var(--border-default)'}`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <FileText size={14} style={{ color: 'var(--text-tertiary)' }} />
                          <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)' }}>
                            {doc.filename}
                          </span>
                        </div>
                        <div
                          style={{
                            width: 16,
                            height: 16,
                            borderRadius: 'var(--radius-xs)',
                            border: `1px solid ${isChecked ? 'var(--accent-primary)' : 'var(--border-strong)'}`,
                            backgroundColor: isChecked ? 'var(--accent-primary)' : 'transparent',
                            color: '#ffffff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {isChecked && <Check size={11} />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn btn-primary btn-sm" onClick={() => setSelectedCol(null)}>
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

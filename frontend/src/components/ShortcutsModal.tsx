import React from 'react';
import { X, Keyboard } from 'lucide-react';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const shortcuts = [
    { key: '⌘ K / Ctrl K', desc: 'Open Command Palette & Global Search' },
    { key: 'Enter', desc: 'Send chat query in conversation' },
    { key: 'Shift + Enter', desc: 'Add new line in chat composer' },
    { key: 'Esc', desc: 'Close modals, drawers, or command palette' },
    { key: '?', desc: 'Open this keyboard shortcuts cheatsheet' },
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Keyboard size={16} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ margin: 0 }}>Keyboard Shortcuts</h3>
          </div>
          <button className="btn btn-ghost btn-xs" onClick={onClose}>
            <X size={14} />
          </button>
        </div>
        <div className="modal-body" style={{ padding: '12px 18px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {shortcuts.map((s, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--bg-subtle)',
                  border: '1px solid var(--border-default)',
                }}
              >
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{s.desc}</span>
                <kbd className="command-shortcut" style={{ fontSize: 12 }}>{s.key}</kbd>
              </div>
            ))}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

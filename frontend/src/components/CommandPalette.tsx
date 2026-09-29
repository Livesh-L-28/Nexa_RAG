import React, { useState, useEffect, useRef } from 'react';
import {
  LucideIcon,
  Search,
  MessageSquare,
  FileText,
  FolderKanban,
  Binary,
  Cpu,
  Database,
  BarChart3,
  ShieldAlert,
  Users,
  Activity,
  ScrollText,
  Upload,
  Sun,
  Moon,
  LogOut,
  X,
} from 'lucide-react';
import { NavigationTab } from '../types';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (tab: NavigationTab) => void;
  onOpenUpload: () => void;
}

interface CommandItem {
  id: string;
  label: string;
  group: 'Navigation' | 'Actions' | 'Preferences';
  icon: LucideIcon;
  shortcut?: string;
  adminOnly?: boolean;
  action: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onOpenUpload,
}) => {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = [
    {
      id: 'nav-overview',
      label: 'Go to Overview',
      group: 'Navigation',
      icon: BarChart3,
      shortcut: 'G O',
      action: () => onNavigate('overview'),
    },
    {
      id: 'nav-chat',
      label: 'Go to Chat & SSE Streaming',
      group: 'Navigation',
      icon: MessageSquare,
      shortcut: 'G C',
      action: () => onNavigate('chat'),
    },
    {
      id: 'nav-docs',
      label: 'Go to Documents',
      group: 'Navigation',
      icon: FileText,
      shortcut: 'G D',
      action: () => onNavigate('documents'),
    },
    {
      id: 'action-upload',
      label: 'Upload New Document',
      group: 'Actions',
      icon: Upload,
      shortcut: 'U',
      action: () => onOpenUpload(),
    },
    {
      id: 'nav-collections',
      label: 'Go to Collections',
      group: 'Navigation',
      icon: FolderKanban,
      action: () => onNavigate('collections'),
    },
    {
      id: 'nav-inspector',
      label: 'Open Retrieval Inspector',
      group: 'Navigation',
      icon: Binary,
      action: () => onNavigate('inspector'),
    },
    {
      id: 'nav-memory',
      label: 'Go to Memory (MAG)',
      group: 'Navigation',
      icon: Cpu,
      action: () => onNavigate('memory'),
    },
    {
      id: 'nav-cache',
      label: 'Go to Cache (CAG)',
      group: 'Navigation',
      icon: Database,
      action: () => onNavigate('cache'),
    },
    {
      id: 'nav-analytics',
      label: 'Go to Analytics & Telemetry',
      group: 'Navigation',
      icon: BarChart3,
      action: () => onNavigate('analytics'),
    },
    {
      id: 'nav-security',
      label: 'Open Security & Guardrails Center',
      group: 'Navigation',
      icon: ShieldAlert,
      adminOnly: true,
      action: () => onNavigate('security'),
    },
    {
      id: 'nav-users',
      label: 'Manage Platform Users & Roles',
      group: 'Navigation',
      icon: Users,
      adminOnly: true,
      action: () => onNavigate('users'),
    },
    {
      id: 'nav-system',
      label: 'View System Health & Probes',
      group: 'Navigation',
      icon: Activity,
      adminOnly: true,
      action: () => onNavigate('system'),
    },
    {
      id: 'nav-audit',
      label: 'View Audit Logs',
      group: 'Navigation',
      icon: ScrollText,
      adminOnly: true,
      action: () => onNavigate('audit'),
    },
    {
      id: 'action-theme',
      label: theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme',
      group: 'Preferences',
      icon: theme === 'dark' ? Sun : Moon,
      shortcut: 'T',
      action: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
    },
    {
      id: 'action-logout',
      label: 'Log out of NexaRAG',
      group: 'Preferences',
      icon: LogOut,
      action: () => logout(),
    },
  ];

  const filteredCommands = commands.filter((c) => {
    if (c.adminOnly && user?.role !== 'ADMIN') return false;
    if (!query.trim()) return true;
    return (
      c.label.toLowerCase().includes(query.toLowerCase()) ||
      c.group.toLowerCase().includes(query.toLowerCase())
    );
  });

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filteredCommands.length || 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % (filteredCommands.length || 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredCommands[selectedIndex]) {
          filteredCommands[selectedIndex].action();
          onClose();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex, onClose]);

  if (!isOpen) return null;

  return (
    <div className="command-backdrop" onClick={onClose}>
      <div className="command-box" onClick={(e) => e.stopPropagation()}>
        <div className="command-input-row">
          <Search size={16} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
          <input
            ref={inputRef}
            className="command-input"
            placeholder="Type a command or search sections..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn btn-ghost btn-xs" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="command-list">
          {filteredCommands.length === 0 ? (
            <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No commands found matching "{query}"
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => {
              const Icon = cmd.icon;
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={cmd.id}
                  className={`command-item ${isSelected ? 'selected' : ''}`}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onClick={() => {
                    cmd.action();
                    onClose();
                  }}
                >
                  <div className="command-item-left">
                    <Icon size={14} style={{ color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)' }} />
                    <span>{cmd.label}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{cmd.group}</span>
                    {cmd.shortcut && <kbd className="command-shortcut">{cmd.shortcut}</kbd>}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div
          style={{
            padding: '8px 14px',
            borderTop: '1px solid var(--border-default)',
            fontSize: '11px',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'var(--bg-subtle)',
          }}
        >
          <span>Use ↑ ↓ to navigate, Enter to select, Esc to close</span>
          <span>NexaRAG Command v1.0</span>
        </div>
      </div>
    </div>
  );
};

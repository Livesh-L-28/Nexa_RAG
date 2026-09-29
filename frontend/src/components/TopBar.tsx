import React, { useState, useEffect } from 'react';
import {
  Search,
  Bell,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Upload,
  ChevronRight,
  Shield,
  Layers,
} from 'lucide-react';
import { NavigationTab, SystemHealth } from '../types';
import { api } from '../api/client';
import { NotificationsPopover, NotificationItem } from './NotificationsPopover';

interface TopBarProps {
  currentTab: NavigationTab;
  onOpenCommand: () => void;
  onOpenUpload: () => void;
  onNavigate: (tab: NavigationTab) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentTab,
  onOpenCommand,
  onOpenUpload,
  onNavigate,
}) => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([
    {
      id: '1',
      type: 'success',
      title: 'PostgreSQL + pgvector ready',
      message: 'Vector index and cosine search initialized.',
      timestamp: 'Just now',
      read: false,
    },
    {
      id: '2',
      type: 'info',
      title: 'Context Orchestration active',
      message: '7-tier priority fusion layer active with 6k token budget.',
      timestamp: '5m ago',
      read: false,
    },
    {
      id: '3',
      type: 'security',
      title: 'NeMo Guardrails enabled',
      message: '3-tier fail-closed security pipeline online.',
      timestamp: '10m ago',
      read: true,
    },
  ]);

  useEffect(() => {
    let mounted = true;
    async function checkHealth() {
      try {
        const res = await api.health.checkReady();
        if (mounted) setHealth(res);
      } catch {
        if (mounted) {
          setHealth({
            status: 'not_ready',
            database: 'unreachable',
            vector_support: false,
            llm_provider: 'offline',
            timestamp: new Date().toISOString(),
          });
        }
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const getTabLabel = (tab: NavigationTab) => {
    switch (tab) {
      case 'overview':
        return 'Overview';
      case 'chat':
        return 'Chat & Retrieval';
      case 'documents':
        return 'Document Intelligence';
      case 'collections':
        return 'Collections';
      case 'inspector':
        return 'Retrieval Inspector';
      case 'memory':
        return 'Memory (MAG)';
      case 'cache':
        return 'Cache (CAG)';
      case 'analytics':
        return 'Analytics & Telemetry';
      case 'security':
        return 'Security & Guardrails';
      case 'users':
        return 'User Management';
      case 'system':
        return 'System Health & Probes';
      case 'audit':
        return 'Audit Logs';
      default:
        return 'Platform';
    }
  };

  const getStatusBadge = () => {
    if (!health) {
      return (
        <div className="badge badge-neutral" style={{ fontSize: 11, gap: 5 }}>
          <span className="status-dot status-dot-neutral" />
          <span>Connecting...</span>
        </div>
      );
    }
    if (health.status === 'ready') {
      return (
        <div
          className="badge badge-success"
          style={{ fontSize: 11, gap: 5, cursor: 'pointer' }}
          onClick={() => onNavigate('system')}
          title="Click to view detailed system health"
        >
          <span className="status-dot status-dot-success" />
          <span>Operational</span>
        </div>
      );
    }
    return (
      <div
        className="badge badge-warning"
        style={{ fontSize: 11, gap: 5, cursor: 'pointer' }}
        onClick={() => onNavigate('system')}
        title="Database or vector provider degraded"
      >
        <span className="status-dot status-dot-warning" />
        <span>Degraded</span>
      </div>
    );
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <header
      style={{
        height: 52,
        backgroundColor: 'var(--bg-card)',
        borderBottom: '1px solid var(--border-default)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        position: 'sticky',
        top: 0,
        zIndex: 90,
      }}
    >
      {/* Left: Breadcrumbs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
        <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>NexaRAG</span>
        <ChevronRight size={13} style={{ color: 'var(--text-muted)' }} />
        <span
          style={{
            color: 'var(--text-secondary)',
            fontWeight: 500,
            cursor: 'pointer',
          }}
          onClick={() => onNavigate('overview')}
        >
          Enterprise
        </span>
        <ChevronRight size={13} style={{ color: 'var(--text-muted)' }} />
        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{getTabLabel(currentTab)}</span>
      </div>

      {/* Right Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* Global Search / Command Palette trigger */}
        <button
          className="btn btn-secondary btn-sm"
          onClick={onOpenCommand}
          style={{
            height: 30,
            padding: '0 10px',
            gap: 12,
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-input)',
            fontSize: 12,
          }}
          title="Global Search & Commands (⌘K)"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Search size={13} style={{ color: 'var(--text-muted)' }} />
            <span>Search or jump to...</span>
          </div>
          <kbd className="command-shortcut" style={{ fontSize: 10.5, padding: '1px 4px' }}>⌘K</kbd>
        </button>

        {/* Quick Upload Button */}
        <button
          className="btn btn-secondary btn-sm"
          onClick={onOpenUpload}
          style={{ height: 30, padding: '0 9px', fontSize: 12 }}
          title="Upload new document (PDF, DOCX, TXT)"
        >
          <Upload size={13} style={{ color: 'var(--text-secondary)' }} />
          <span>Upload</span>
        </button>

        {/* System Health Status */}
        {getStatusBadge()}

        {/* Notifications Popover */}
        <div style={{ position: 'relative' }}>
          <button
            className="btn btn-ghost btn-sm btn-icon"
            onClick={() => setIsNotifOpen((prev) => !prev)}
            title="Notifications"
            style={{ position: 'relative' }}
          >
            <Bell size={15} style={{ color: 'var(--text-secondary)' }} />
            {unreadCount > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: 'var(--accent-primary)',
                }}
              />
            )}
          </button>

          <NotificationsPopover
            isOpen={isNotifOpen}
            onClose={() => setIsNotifOpen(false)}
            notifications={notifications}
            onMarkAllRead={() => {
              setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
            }}
            onClear={() => setNotifications([])}
          />
        </div>
      </div>
    </header>
  );
};

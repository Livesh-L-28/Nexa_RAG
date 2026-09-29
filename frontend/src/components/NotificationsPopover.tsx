import React from 'react';
import { Bell, CheckCircle2, ShieldAlert, FileText, X } from 'lucide-react';

export interface NotificationItem {
  id: string;
  type: 'info' | 'success' | 'warning' | 'security';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

interface NotificationsPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: NotificationItem[];
  onMarkAllRead: () => void;
  onClear: () => void;
}

export const NotificationsPopover: React.FC<NotificationsPopoverProps> = ({
  isOpen,
  onClose,
  notifications,
  onMarkAllRead,
  onClear,
}) => {
  if (!isOpen) return null;

  const getIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 size={14} style={{ color: 'var(--status-success)' }} />;
      case 'security':
        return <ShieldAlert size={14} style={{ color: 'var(--status-error)' }} />;
      case 'warning':
        return <ShieldAlert size={14} style={{ color: 'var(--status-warning)' }} />;
      default:
        return <FileText size={14} style={{ color: 'var(--status-info)' }} />;
    }
  };

  return (
    <div
      style={{
        position: 'absolute',
        top: '100%',
        right: 0,
        marginTop: 6,
        width: 340,
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border-default)',
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow-dropdown)',
        zIndex: 500,
        overflow: 'hidden',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <div
        style={{
          padding: '10px 14px',
          borderBottom: '1px solid var(--border-default)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Bell size={14} style={{ color: 'var(--text-secondary)' }} />
          <span style={{ fontSize: 12.5, fontWeight: 600 }}>Notifications</span>
          {notifications.filter((n) => !n.read).length > 0 && (
            <span className="badge badge-info" style={{ fontSize: 10, padding: '1px 5px' }}>
              {notifications.filter((n) => !n.read).length} new
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button className="btn btn-ghost btn-xs" onClick={onMarkAllRead} style={{ fontSize: 11 }}>
            Mark read
          </button>
          <button className="btn btn-ghost btn-xs" onClick={onClose}>
            <X size={13} />
          </button>
        </div>
      </div>

      <div style={{ maxHeight: 300, overflowY: 'auto' }}>
        {notifications.length === 0 ? (
          <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12.5 }}>
            No recent notifications
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--border-subtle)',
                backgroundColor: n.read ? 'transparent' : 'var(--bg-surface-hover)',
                display: 'flex',
                gap: 10,
                alignItems: 'flex-start',
              }}
            >
              <div style={{ marginTop: 2 }}>{getIcon(n.type)}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)' }}>{n.title}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 2 }}>{n.message}</div>
                <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 4 }}>{n.timestamp}</div>
              </div>
            </div>
          ))
        )}
      </div>

      {notifications.length > 0 && (
        <div
          style={{
            padding: '6px 12px',
            borderTop: '1px solid var(--border-default)',
            textAlign: 'right',
            backgroundColor: 'var(--bg-subtle)',
          }}
        >
          <button className="btn btn-ghost btn-xs" onClick={onClear} style={{ fontSize: 11 }}>
            Clear all
          </button>
        </div>
      )}
    </div>
  );
};

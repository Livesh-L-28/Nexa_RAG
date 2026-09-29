import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  MessageSquare,
  FileText,
  FolderKanban,
  Binary,
  Cpu,
  Database,
  BarChart3,
  ShieldCheck,
  Users,
  Activity,
  ScrollText,
  Sun,
  Moon,
  Monitor,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Keyboard,
  Building2,
} from 'lucide-react';
import { NavigationTab } from '../types';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

interface SidebarProps {
  currentTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
  onOpenShortcuts: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  onOpenShortcuts,
}) => {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('nexarag_sidebar_collapsed') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('nexarag_sidebar_collapsed', String(isCollapsed));
  }, [isCollapsed]);

  const toggleCollapse = () => setIsCollapsed((prev) => !prev);

  const mainNav = [
    { id: 'overview' as NavigationTab, label: 'Overview', icon: LayoutDashboard },
    { id: 'chat' as NavigationTab, label: 'Chat & Streaming', icon: MessageSquare },
    { id: 'documents' as NavigationTab, label: 'Documents', icon: FileText },
    { id: 'collections' as NavigationTab, label: 'Collections', icon: FolderKanban },
    { id: 'inspector' as NavigationTab, label: 'Retrieval Inspector', icon: Binary },
    { id: 'memory' as NavigationTab, label: 'Memory (MAG)', icon: Cpu },
    { id: 'cache' as NavigationTab, label: 'Cache (CAG)', icon: Database },
    { id: 'analytics' as NavigationTab, label: 'Analytics', icon: BarChart3 },
  ];

  const adminNav = [
    { id: 'security' as NavigationTab, label: 'Security Center', icon: ShieldCheck },
    { id: 'users' as NavigationTab, label: 'Users & Roles', icon: Users },
    { id: 'system' as NavigationTab, label: 'System Health', icon: Activity },
    { id: 'audit' as NavigationTab, label: 'Audit Logs', icon: ScrollText },
  ];

  const getInitials = (email: string) => {
    return email ? email.substring(0, 2).toUpperCase() : 'US';
  };

  const cycleTheme = () => {
    if (theme === 'dark') setTheme('light');
    else if (theme === 'light') setTheme('system');
    else setTheme('dark');
  };

  const getThemeIcon = () => {
    if (theme === 'dark') return <Moon size={14} />;
    if (theme === 'light') return <Sun size={14} />;
    return <Monitor size={14} />;
  };

  return (
    <aside
      style={{
        width: isCollapsed ? 64 : 240,
        backgroundColor: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-default)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'width 0.15s ease',
        flexShrink: 0,
        height: '100vh',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      {/* Top Header / Workspace Info */}
      <div>
        <div
          style={{
            height: 52,
            borderBottom: '1px solid var(--border-default)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: isCollapsed ? 'center' : 'space-between',
            padding: isCollapsed ? '0' : '0 14px',
          }}
        >
          {!isCollapsed ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: 'var(--radius-xs)',
                  backgroundColor: 'var(--accent-primary)',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 700,
                  fontSize: 12,
                  flexShrink: 0,
                }}
              >
                N
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    letterSpacing: '-0.01em',
                    lineHeight: 1.2,
                    whiteSpace: 'nowrap',
                    textOverflow: 'ellipsis',
                    overflow: 'hidden',
                  }}
                >
                  NexaRAG
                </span>
                <span
                  style={{
                    fontSize: 10.5,
                    color: 'var(--text-tertiary)',
                    lineHeight: 1.2,
                    whiteSpace: 'nowrap',
                  }}
                >
                  Enterprise Document Intelligence
                </span>
              </div>
            </div>
          ) : (
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'var(--accent-primary)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: 13,
              }}
              title="NexaRAG Enterprise"
            >
              N
            </div>
          )}

          {!isCollapsed && (
            <button
              className="btn btn-ghost btn-xs"
              onClick={toggleCollapse}
              title="Collapse sidebar"
              style={{ padding: 4 }}
            >
              <ChevronLeft size={14} />
            </button>
          )}
        </div>

        {/* User Identity Box */}
        {!isCollapsed ? (
          <div
            style={{
              padding: '10px 14px',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              gap: 9,
            }}
          >
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                backgroundColor: 'var(--bg-subtle)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10.5,
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {getInitials(user?.email || '')}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: 'var(--text-primary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
                title={user?.email}
              >
                {user?.email || 'User'}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 1 }}>
                <span
                  className={`badge ${user?.role === 'ADMIN' ? 'badge-info' : 'badge-neutral'}`}
                  style={{ fontSize: 9.5, padding: '0 4px', textTransform: 'uppercase' }}
                >
                  {user?.role || 'USER'}
                </span>
                <span style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>Tenant: Live</span>
              </div>
            </div>
          </div>
        ) : (
          <div
            style={{
              padding: '8px 0',
              display: 'flex',
              justifyContent: 'center',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                backgroundColor: 'var(--bg-subtle)',
                border: '1px solid var(--border-default)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10.5,
                fontWeight: 600,
              }}
              title={`${user?.email} (${user?.role})`}
            >
              {getInitials(user?.email || '')}
            </div>
          </div>
        )}

        {/* Main Navigation Links */}
        <div style={{ padding: '8px 6px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {!isCollapsed && (
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                padding: '4px 8px 2px',
              }}
            >
              Navigation
            </div>
          )}

          {mainNav.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                title={isCollapsed ? item.label : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 9,
                  padding: isCollapsed ? '8px 0' : '6px 10px',
                  justifyContent: isCollapsed ? 'center' : 'flex-start',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: isActive ? 'var(--bg-surface-active)' : 'transparent',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 12.5,
                  fontWeight: isActive ? 600 : 400,
                  textAlign: 'left',
                  width: '100%',
                  transition: 'background-color 0.1s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <Icon
                  size={15}
                  style={{
                    color: isActive ? 'var(--accent-primary)' : 'var(--text-tertiary)',
                    flexShrink: 0,
                  }}
                />
                {!isCollapsed && <span>{item.label}</span>}
              </button>
            );
          })}

          {/* Admin Navigation */}
          {user?.role === 'ADMIN' && (
            <>
              {!isCollapsed && (
                <div
                  style={{
                    fontSize: 10.5,
                    fontWeight: 600,
                    color: 'var(--text-tertiary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    padding: '12px 8px 2px',
                  }}
                >
                  Administration
                </div>
              )}
              {adminNav.map((item) => {
                const Icon = item.icon;
                const isActive = currentTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onTabChange(item.id)}
                    title={isCollapsed ? item.label : undefined}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 9,
                      padding: isCollapsed ? '8px 0' : '6px 10px',
                      justifyContent: isCollapsed ? 'center' : 'flex-start',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: isActive ? 'var(--bg-surface-active)' : 'transparent',
                      color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: 12.5,
                      fontWeight: isActive ? 600 : 400,
                      textAlign: 'left',
                      width: '100%',
                      transition: 'background-color 0.1s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)';
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <Icon
                      size={15}
                      style={{
                        color: isActive ? 'var(--accent-primary)' : 'var(--text-tertiary)',
                        flexShrink: 0,
                      }}
                    />
                    {!isCollapsed && <span>{item.label}</span>}
                  </button>
                );
              })}
            </>
          )}
        </div>
      </div>

      {/* Bottom Actions & Controls */}
      <div
        style={{
          borderTop: '1px solid var(--border-default)',
          padding: '6px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {isCollapsed && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={toggleCollapse}
            title="Expand sidebar"
            style={{ width: '100%', justifyContent: 'center', padding: '6px 0' }}
          >
            <ChevronRight size={14} />
          </button>
        )}

        <button
          className="btn btn-ghost btn-sm"
          onClick={onOpenShortcuts}
          title="Keyboard shortcuts (?)"
          style={{
            width: '100%',
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            fontSize: 12,
            padding: isCollapsed ? '6px 0' : '6px 8px',
          }}
        >
          <Keyboard size={14} style={{ color: 'var(--text-tertiary)' }} />
          {!isCollapsed && <span>Shortcuts (?)</span>}
        </button>

        <button
          className="btn btn-ghost btn-sm"
          onClick={cycleTheme}
          title={`Theme: ${theme.toUpperCase()} (Click to toggle)`}
          style={{
            width: '100%',
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            fontSize: 12,
            padding: isCollapsed ? '6px 0' : '6px 8px',
          }}
        >
          {getThemeIcon()}
          {!isCollapsed && <span style={{ textTransform: 'capitalize' }}>Theme: {theme}</span>}
        </button>

        <button
          className="btn btn-ghost btn-sm"
          onClick={logout}
          title="Log out"
          style={{
            width: '100%',
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            fontSize: 12,
            color: 'var(--status-error)',
            padding: isCollapsed ? '6px 0' : '6px 8px',
          }}
        >
          <LogOut size={14} />
          {!isCollapsed && <span>Log out</span>}
        </button>
      </div>
    </aside>
  );
};

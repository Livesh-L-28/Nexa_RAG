import React, { useEffect, useState } from 'react';
import { Sparkles, LayoutDashboard, FileText, MessageSquare, LogOut, ShieldCheck, Activity } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

interface NavbarProps {
  currentTab: 'dashboard' | 'documents' | 'chat';
  onTabChange: (tab: 'dashboard' | 'documents' | 'chat') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onTabChange }) => {
  const { user, logout } = useAuth();
  const [systemReady, setSystemReady] = useState<boolean>(true);

  useEffect(() => {
    api.health.check()
      .then((res) => setSystemReady(res.status === 'ready'))
      .catch(() => setSystemReady(false));
  }, []);

  return (
    <header className="app-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
        <div className="logo-group" style={{ cursor: 'pointer' }} onClick={() => onTabChange('dashboard')}>
          <div className="logo-icon">
            <Sparkles size={20} />
          </div>
          <div>
            <span className="gradient-text">NexaRAG</span>
            <span style={{ fontSize: '0.7rem', display: 'block', color: 'var(--text-muted)', fontWeight: 500, letterSpacing: '0.05em' }}>
              DOCUMENT INTELLIGENCE
            </span>
          </div>
        </div>

        <nav className="nav-links">
          <button
            className={`nav-item ${currentTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => onTabChange('dashboard')}
          >
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </button>
          <button
            className={`nav-item ${currentTab === 'documents' ? 'active' : ''}`}
            onClick={() => onTabChange('documents')}
          >
            <FileText size={18} />
            <span>Documents</span>
          </button>
          <button
            className={`nav-item ${currentTab === 'chat' ? 'active' : ''}`}
            onClick={() => onTabChange('chat')}
          >
            <MessageSquare size={18} />
            <span>RAG Chat</span>
          </button>
        </nav>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
        {/* System Health Status */}
        <div className="metric-pill" title="Backend & Vector Engine Status">
          <span className={systemReady ? 'pulse-dot' : ''} style={!systemReady ? { width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-rose)' } : {}} />
          <Activity size={13} style={{ color: systemReady ? 'var(--accent-emerald)' : 'var(--accent-rose)' }} />
          <span>{systemReady ? 'pgvector ready' : 'connecting'}</span>
        </div>

        {/* User Info & Role */}
        {user && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                {user.email.split('@')[0]}
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <span className={`badge ${user.role === 'ADMIN' ? 'badge-info' : 'badge-success'}`}>
                  {user.role}
                </span>
              </div>
            </div>

            <button
              className="btn btn-secondary btn-sm"
              onClick={logout}
              title="Sign out of account"
              style={{ padding: '0.5rem', borderRadius: 'var(--radius-md)' }}
            >
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { NavigationTab } from './types';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { CommandPalette } from './components/CommandPalette';
import { ShortcutsModal } from './components/ShortcutsModal';
import { UploadDrawer } from './components/UploadDrawer';

import { AuthPage } from './pages/AuthPage';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { ChatPage } from './pages/ChatPage';
import { CollectionsPage } from './pages/CollectionsPage';
import { RetrievalInspectorPage } from './pages/RetrievalInspectorPage';
import { MemoryPage } from './pages/MemoryPage';
import { CachePage } from './pages/CachePage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { SecurityPage } from './pages/SecurityPage';
import { UsersPage } from './pages/UsersPage';
import { SystemHealthPage } from './pages/SystemHealthPage';
import { AuditLogPage } from './pages/AuditLogPage';

import { ShieldAlert } from 'lucide-react';

const AdminRestrictedView: React.FC<{ tabName: string; onReturn: () => void }> = ({
  tabName,
  onReturn,
}) => (
  <div style={{ padding: '64px 32px', maxWidth: 580, margin: '0 auto', textAlign: 'center' }}>
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 56,
        height: 56,
        borderRadius: '50%',
        backgroundColor: 'var(--status-warning-subtle)',
        color: 'var(--status-warning)',
        marginBottom: 20,
      }}
    >
      <ShieldAlert size={28} />
    </div>
    <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
      Administrator Access Required
    </h2>
    <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 24 }}>
      The <strong>{tabName}</strong> console is restricted to platform administrators. 
      Your current session is authenticated as a standard enterprise <strong>USER</strong> (Analyst / Knowledge Worker). 
      To access security governance, RBAC controls, or system diagnostics, please sign in with an Administrator account.
    </p>
    <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
      <button className="btn btn-primary btn-sm" onClick={onReturn}>
        Return to Overview
      </button>
    </div>
  </div>
);

const MainLayout: React.FC = () => {
  const { user, loading } = useAuth();
  const [currentTab, setCurrentTab] = useState<NavigationTab>('overview');
  const [isCommandOpen, setIsCommandOpen] = useState(false);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Global Keyboard shortcuts: ⌘K / Ctrl+K and ?
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandOpen((prev) => !prev);
      }
      // ? for shortcuts (when not typing in input/textarea)
      if (
        e.key === '?' &&
        !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)
      ) {
        e.preventDefault();
        setIsShortcutsOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 12,
          backgroundColor: 'var(--bg-app)',
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--accent-primary)',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: 16,
          }}
        >
          N
        </div>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Authenticating NexaRAG Enterprise...
        </span>
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-app)' }}>
      {/* Left Application Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
      />

      {/* Main View Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <TopBar
          currentTab={currentTab}
          onOpenCommand={() => setIsCommandOpen(true)}
          onOpenUpload={() => setIsUploadOpen(true)}
          onNavigate={setCurrentTab}
        />

        <main style={{ flex: 1, overflowY: 'auto' }}>
          {currentTab === 'overview' && (
            <DashboardPage
              onNavigate={setCurrentTab}
              onOpenUpload={() => setIsUploadOpen(true)}
            />
          )}
          {currentTab === 'chat' && <ChatPage />}
          {currentTab === 'documents' && <DocumentsPage />}
          {currentTab === 'collections' && <CollectionsPage onNavigate={setCurrentTab} />}
          {currentTab === 'inspector' && <RetrievalInspectorPage />}
          {currentTab === 'memory' && <MemoryPage />}
          {currentTab === 'cache' && <CachePage />}
          {currentTab === 'analytics' && <AnalyticsPage />}
          {currentTab === 'security' && (
            user?.role === 'ADMIN' ? (
              <SecurityPage />
            ) : (
              <AdminRestrictedView
                tabName="Security & Guardrails Center"
                onReturn={() => setCurrentTab('overview')}
              />
            )
          )}
          {currentTab === 'users' && (
            user?.role === 'ADMIN' ? (
              <UsersPage />
            ) : (
              <AdminRestrictedView
                tabName="Users & RBAC Administration"
                onReturn={() => setCurrentTab('overview')}
              />
            )
          )}
          {currentTab === 'system' && (
            user?.role === 'ADMIN' ? (
              <SystemHealthPage />
            ) : (
              <AdminRestrictedView
                tabName="System Health & Infrastructure Probes"
                onReturn={() => setCurrentTab('overview')}
              />
            )
          )}
          {currentTab === 'audit' && (
            user?.role === 'ADMIN' ? (
              <AuditLogPage />
            ) : (
              <AdminRestrictedView
                tabName="Enterprise Compliance Audit Logs"
                onReturn={() => setCurrentTab('overview')}
              />
            )
          )}
        </main>
      </div>

      {/* Global Modals & Drawers */}
      <CommandPalette
        isOpen={isCommandOpen}
        onClose={() => setIsCommandOpen(false)}
        onNavigate={setCurrentTab}
        onOpenUpload={() => setIsUploadOpen(true)}
      />

      <ShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />

      <UploadDrawer
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => {}}
      />
    </div>
  );
};

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <MainLayout />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;

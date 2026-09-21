import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { AuthPage } from './pages/AuthPage';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { ChatPage } from './pages/ChatPage';

const MainLayout: React.FC = () => {
  const { user, loading } = useAuth();
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'documents' | 'chat'>('dashboard');

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '1rem',
      }}>
        <div className="pulse-dot" style={{ width: 16, height: 16 }} />
        <span className="text-secondary" style={{ fontSize: '0.9rem' }}>Initializing NexaRAG Platform...</span>
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navbar currentTab={currentTab} onTabChange={setCurrentTab} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {currentTab === 'dashboard' && <DashboardPage onNavigate={setCurrentTab} />}
        {currentTab === 'documents' && <DocumentsPage />}
        {currentTab === 'chat' && <ChatPage />}
      </div>
    </div>
  );
};

export function App() {
  return (
    <AuthProvider>
      <MainLayout />
    </AuthProvider>
  );
}

export default App;

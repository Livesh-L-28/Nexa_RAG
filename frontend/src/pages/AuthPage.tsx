import React, { useState } from 'react';
import { Sparkles, ArrowRight, Lock, Mail, Shield, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const AuthPage: React.FC = () => {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState<boolean>(true);
  const [email, setEmail] = useState<string>('demo@nexarag.ai');
  const [password, setPassword] = useState<string>('password123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(email, password);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
    }}>
      <div className="glass-panel" style={{
        maxWidth: 440,
        width: '100%',
        padding: '2.5rem',
        position: 'relative',
        zIndex: 2,
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
            color: 'white',
            marginBottom: '1rem',
            boxShadow: '0 4px 16px rgba(99, 102, 241, 0.4)',
          }}>
            <Sparkles size={24} />
          </div>
          <h2>Welcome to <span className="gradient-text">NexaRAG</span></h2>
          <p className="text-secondary" style={{ fontSize: '0.9rem', marginTop: '0.4rem' }}>
            Enterprise AI Document Intelligence & Retrieval Platform
          </p>
        </div>

        {/* Tab switch */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          background: 'rgba(15, 21, 35, 0.6)',
          padding: '4px',
          borderRadius: 'var(--radius-md)',
          marginBottom: '1.5rem',
        }}>
          <button
            type="button"
            className={`btn ${isLogin ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.5rem', border: 'none' }}
            onClick={() => { setIsLogin(true); setError(null); }}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`btn ${!isLogin ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.5rem', border: 'none' }}
            onClick={() => { setIsLogin(false); setError(null); }}
          >
            Create Account
          </button>
        </div>

        {error && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            padding: '0.75rem 1rem',
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: 'var(--radius-md)',
            color: '#fda4af',
            fontSize: '0.85rem',
            marginBottom: '1.25rem',
          }}>
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="email">Email Address</label>
            <div style={{ position: 'relative' }}>
              <Mail size={16} style={{ position: 'absolute', left: 12, top: 14, color: 'var(--text-muted)' }} />
              <input
                id="email"
                type="email"
                required
                className="form-input"
                style={{ paddingLeft: '2.5rem' }}
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{ position: 'absolute', left: 12, top: 14, color: 'var(--text-muted)' }} />
              <input
                id="password"
                type="password"
                required
                minLength={8}
                className="form-input"
                style={{ paddingLeft: '2.5rem' }}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', marginTop: '0.5rem', padding: '0.75rem' }}
            disabled={loading}
          >
            <span>{loading ? 'Authenticating...' : isLogin ? 'Sign In to Workspace' : 'Create New Account'}</span>
            <ArrowRight size={16} />
          </button>
        </form>

        {/* Quick Demo Credentials */}
        <div style={{
          marginTop: '1.75rem',
          paddingTop: '1.25rem',
          borderTop: '1px solid var(--border-subtle)',
          textAlign: 'center',
        }}>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Quick fill demo accounts:
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => { setEmail('demo@nexarag.ai'); setPassword('password123'); }}
            >
              Demo User
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => { setEmail('admin@nexarag.ai'); setPassword('adminpassword123'); }}
            >
              <Shield size={12} />
              Admin
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

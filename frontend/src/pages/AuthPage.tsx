import React, { useState } from 'react';
import { Lock, Mail, ArrowRight, AlertCircle, ShieldCheck } from 'lucide-react';
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
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const setPreset = (presetEmail: string, presetPw: string) => {
    setEmail(presetEmail);
    setPassword(presetPw);
    setError(null);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        backgroundColor: 'var(--bg-app)',
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: 400,
          width: '100%',
          padding: 32,
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--accent-primary)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: 16,
              margin: '0 auto 12px',
            }}
          >
            N
          </div>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            NexaRAG Enterprise
          </h1>
          <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginTop: 4 }}>
            Document Intelligence & Retrieval-Augmented Generation
          </p>
        </div>

        {/* Tab Toggle: Login vs Register */}
        <div
          style={{
            display: 'flex',
            backgroundColor: 'var(--bg-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: 3,
            marginBottom: 20,
            border: '1px solid var(--border-default)',
          }}
        >
          <button
            type="button"
            className={`btn btn-xs ${isLogin ? 'btn-secondary' : 'btn-ghost'}`}
            onClick={() => {
              setIsLogin(true);
              setError(null);
            }}
            style={{
              flex: 1,
              fontWeight: isLogin ? 600 : 400,
              backgroundColor: isLogin ? 'var(--bg-surface)' : 'transparent',
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`btn btn-xs ${!isLogin ? 'btn-secondary' : 'btn-ghost'}`}
            onClick={() => {
              setIsLogin(false);
              setError(null);
            }}
            style={{
              flex: 1,
              fontWeight: !isLogin ? 600 : 400,
              backgroundColor: !isLogin ? 'var(--bg-surface)' : 'transparent',
            }}
          >
            Create Account
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            style={{
              marginBottom: 16,
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--status-error-bg)',
              color: 'var(--status-error)',
              border: '1px solid var(--status-error-border)',
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <AlertCircle size={14} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--text-secondary)',
                display: 'block',
                marginBottom: 6,
              }}
            >
              Work Email
            </label>
            <div style={{ position: 'relative' }}>
              <Mail
                size={14}
                style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }}
              />
              <input
                type="email"
                required
                className="input"
                placeholder="name@enterprise.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ paddingLeft: 32 }}
              />
            </div>
          </div>

          <div>
            <label
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--text-secondary)',
                display: 'block',
                marginBottom: 6,
              }}
            >
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <Lock
                size={14}
                style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }}
              />
              <input
                type="password"
                required
                className="input"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ paddingLeft: 32 }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={loading}
            style={{ marginTop: 6, width: '100%', height: 36, fontSize: 13 }}
          >
            <span>{loading ? 'Authenticating...' : isLogin ? 'Sign In to Workspace' : 'Register Account'}</span>
            {!loading && <ArrowRight size={14} />}
          </button>
        </form>

        {/* Fast Credentials Quick-Fill for Testing & Demos */}
        <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-default)' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase' }}>
            Demo Accounts (Click to Fill)
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={() => setPreset('demo@nexarag.ai', 'password123')}
              style={{ flex: 1, fontSize: 11 }}
            >
              Demo User
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={() => setPreset('admin@nexarag.ai', 'adminpassword123')}
              style={{ flex: 1, fontSize: 11 }}
            >
              Platform Admin
            </button>
          </div>
        </div>

        {/* Security Footer Notice */}
        <div
          style={{
            marginTop: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            fontSize: 11,
            color: 'var(--text-muted)',
          }}
        >
          <ShieldCheck size={13} style={{ color: 'var(--status-success)' }} />
          <span>Stateless HS256 JWT with tenant isolation</span>
        </div>
      </div>
    </div>
  );
};

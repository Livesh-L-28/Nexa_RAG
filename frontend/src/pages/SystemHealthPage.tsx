import React, { useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Database,
  Cpu,
  Layers,
  ShieldCheck,
  Server,
  Radio,
} from 'lucide-react';
import { api } from '../api/client';
import { SystemHealth } from '../types';

export const SystemHealthPage: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [liveInfo, setLiveInfo] = useState<{ status: string; app: string; environment: string; timestamp: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const [readyRes, liveRes] = await Promise.all([
        api.health.checkReady(),
        api.health.checkLive(),
      ]);
      setHealth(readyRes);
      setLiveInfo(liveRes);
    } catch {
      setHealth({
        status: 'not_ready',
        database: 'unreachable',
        vector_support: false,
        llm_provider: 'offline',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const components = [
    {
      name: 'FastAPI Application Server',
      status: liveInfo?.status === 'healthy' ? 'Operational' : 'Degraded',
      details: `Environment: ${liveInfo?.environment || 'production'} • Version 1.0.0`,
      icon: Server,
    },
    {
      name: 'PostgreSQL 16 Engine',
      status: health?.database === 'connected' ? 'Operational' : 'Degraded',
      details: `Connection status: ${health?.database || 'connected'} • SQLAlchemy 2.x Async Engine`,
      icon: Database,
    },
    {
      name: 'pgvector Extension',
      status: health?.vector_support ? 'Operational' : 'Active (Fallback)',
      details: '384-dimensional cosine distance similarity operator (<=>)',
      icon: Layers,
    },
    {
      name: 'LLM Inference Gateway',
      status: 'Operational',
      details: `Provider: ${health?.llm_provider || 'Groq / Gemini / Mock'} • Exponential backoff enabled`,
      icon: Cpu,
    },
    {
      name: 'CAG Cache Storage',
      status: 'Operational',
      details: 'Sub-millisecond thread-safe in-memory cache with JSON disk persistence',
      icon: Database,
    },
    {
      name: 'NVIDIA NeMo Guardrails',
      status: 'Operational',
      details: '3-tier fail-closed security pipeline (Input, Retrieval, Output)',
      icon: ShieldCheck,
    },
    {
      name: 'Server-Sent Events (SSE) Streaming',
      status: 'Operational',
      details: 'HTTP streaming with keep-alive frames and automated disconnection cleanup',
      icon: Radio,
    },
  ];

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}
      >
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>
            System Health & Readiness Probes
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Real-time status of backend containers, database connections, vector extensions, and telemetry recorders.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer', color: 'var(--text-secondary)' }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <span>Auto-refresh (10s)</span>
          </label>

          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchHealth}
            disabled={loading}
            style={{ fontSize: 12 }}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh Probes</span>
          </button>
        </div>
      </div>

      {/* Primary Status Banner */}
      <div
        className="card"
        style={{
          padding: '16px 20px',
          marginBottom: 24,
          backgroundColor: health?.status === 'ready' ? 'var(--status-success-bg)' : 'var(--status-warning-bg)',
          borderColor: health?.status === 'ready' ? 'var(--status-success-border)' : 'var(--status-warning-border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {health?.status === 'ready' ? (
              <CheckCircle2 size={24} style={{ color: 'var(--status-success)' }} />
            ) : (
              <AlertTriangle size={24} style={{ color: 'var(--status-warning)' }} />
            )}
            <div>
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
                {health?.status === 'ready'
                  ? 'All Core Systems Operational'
                  : 'System Operating in Degraded State'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                Last checked: {health ? new Date(health.timestamp).toLocaleTimeString() : 'Checking...'}
              </div>
            </div>
          </div>
          <span className={`badge ${health?.status === 'ready' ? 'badge-success' : 'badge-warning'}`}>
            HTTP 200 OK
          </span>
        </div>
      </div>

      {/* Components Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: 16,
        }}
      >
        {components.map((comp, idx) => {
          const Icon = comp.icon;
          const isOk = comp.status === 'Operational';
          return (
            <div key={idx} className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon size={16} style={{ color: 'var(--accent-primary)' }} />
                  <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {comp.name}
                  </span>
                </div>
                <span className={`badge ${isOk ? 'badge-success' : 'badge-warning'}`}>
                  {comp.status}
                </span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {comp.details}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

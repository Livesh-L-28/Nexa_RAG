import {
  AuditLog,
  CacheEntry,
  CacheStats,
  ChatMessage,
  ChatResponse,
  ChatSession,
  Citation,
  Document,
  MemoryRecord,
  MemoryStats,
  OverviewMetrics,
  RetrievalMetadata,
  SystemHealth,
  User,
} from '../types';

const API_BASE = '/api/v1';

function getToken(): string | null {
  return localStorage.getItem('nexarag_token');
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    (headers as Record<string, string>)['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const text = await response.text();
      try {
        const errorJson = JSON.parse(text);
        if (errorJson?.error?.message) {
          errorMsg = errorJson.error.message;
        } else if (errorJson?.detail) {
          errorMsg = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        if (text && (text.includes('ECONNREFUSED') || text.includes('proxy error') || response.status === 500)) {
          errorMsg = 'Backend server is unreachable. Please ensure the NexaRAG API server is running on http://localhost:8000.';
        } else if (text) {
          errorMsg = text.slice(0, 150);
        }
      }
    } catch {
      // Fallback
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

export const api = {
  auth: {
    login: async (email: string, password: string): Promise<{ access_token: string }> => {
      return request('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
    },
    register: async (email: string, password: string): Promise<User> => {
      return request('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, role: 'USER' }),
      });
    },
    me: async (): Promise<User> => {
      return request('/auth/me');
    },
  },

  documents: {
    list: async (skip = 0, limit = 50): Promise<{ total: number; items: Document[] }> => {
      return request(`/documents?skip=${skip}&limit=${limit}`);
    },
    get: async (id: string): Promise<Document> => {
      return request(`/documents/${id}`);
    },
    upload: async (file: File): Promise<Document> => {
      const formData = new FormData();
      formData.append('file', file);
      return request('/documents/upload', {
        method: 'POST',
        body: formData,
      });
    },
    delete: async (id: string): Promise<{ message: string }> => {
      return request(`/documents/${id}`, {
        method: 'DELETE',
      });
    },
    reprocess: async (id: string): Promise<{ document_id: string; status: string; chunk_count: number; message: string }> => {
      return request(`/documents/${id}/process`, {
        method: 'POST',
      });
    },
  },

  chat: {
    listSessions: async (skip = 0, limit = 50): Promise<ChatSession[]> => {
      return request(`/chat/sessions?skip=${skip}&limit=${limit}`);
    },
    getSession: async (sessionId: string): Promise<ChatSession & { messages: ChatMessage[] }> => {
      return request(`/chat/sessions/${sessionId}`);
    },
    deleteSession: async (sessionId: string): Promise<{ message: string }> => {
      return request(`/chat/sessions/${sessionId}`, {
        method: 'DELETE',
      });
    },
    getSessionLogs: async (sessionId: string): Promise<any[]> => {
      return request(`/chat/sessions/${sessionId}/logs`);
    },
    query: async (query: string, sessionId?: string, documentIds?: string[]): Promise<ChatResponse> => {
      return request('/chat', {
        method: 'POST',
        body: JSON.stringify({ query, session_id: sessionId, document_ids: documentIds }),
      });
    },
    stream: async (
      query: string,
      sessionId?: string,
      documentIds?: string[],
      callbacks?: {
        onInit?: (sessionId: string) => void;
        onToken?: (token: string) => void;
        onDone?: (sources: Citation[], metadata: RetrievalMetadata) => void;
        onError?: (error: string) => void;
        onRedact?: (message: string) => void;
      },
      signal?: AbortSignal
    ) => {
      const token = getToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers,
        signal,
        body: JSON.stringify({
          query,
          session_id: sessionId,
          document_ids: documentIds,
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`Stream error: HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('ReadableStream not supported.');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const jsonStr = trimmed.substring(6);

          try {
            const data = JSON.parse(jsonStr);
            if (data.type === 'init' && callbacks?.onInit) {
              callbacks.onInit(data.session_id);
            } else if (data.type === 'token' && callbacks?.onToken) {
              callbacks.onToken(data.content);
            } else if (data.type === 'done' && callbacks?.onDone) {
              callbacks.onDone(data.sources, data.metadata);
            } else if (data.type === 'redact' && callbacks?.onRedact) {
              callbacks.onRedact(data.message);
            } else if (data.type === 'error' && callbacks?.onError) {
              callbacks.onError(data.message);
            }
          } catch {
            // Ignore parse errors on partial frames
          }
        }
      }
    },
  },

  memory: {
    list: async (type?: string, limit = 50): Promise<MemoryRecord[]> => {
      const q = type ? `?memory_type=${encodeURIComponent(type)}&limit=${limit}` : `?limit=${limit}`;
      return request(`/memory${q}`);
    },
    getStats: async (): Promise<MemoryStats> => {
      return request('/memory/stats');
    },
    create: async (payload: { content: string; memory_type?: string; importance?: number }): Promise<MemoryRecord> => {
      return request('/memory', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    delete: async (memoryId: string): Promise<{ message: string }> => {
      return request(`/memory/${memoryId}`, {
        method: 'DELETE',
      });
    },
    clearAll: async (): Promise<{ message: string }> => {
      return request('/memory', {
        method: 'DELETE',
      });
    },
  },

  cache: {
    getInfo: async (namespace?: string): Promise<{ stats: CacheStats; entries_count: number; entries: CacheEntry[] }> => {
      const q = namespace ? `?namespace=${encodeURIComponent(namespace)}` : '';
      return request(`/cache${q}`);
    },
    invalidate: async (key: string): Promise<{ message: string }> => {
      return request('/cache/invalidate', {
        method: 'POST',
        body: JSON.stringify({ key }),
      });
    },
    preload: async (data: { namespace: string; identifier: string; content: string; ttl_seconds?: number }): Promise<any> => {
      return request('/cache/preload', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    clear: async (): Promise<{ message: string }> => {
      return request('/cache/clear', {
        method: 'POST',
      });
    },
  },

  analytics: {
    getOverview: async (): Promise<OverviewMetrics> => {
      return request('/analytics/overview');
    },
    getAuditLogs: async (skip = 0, limit = 50, method?: string): Promise<{ total: number; items: AuditLog[] }> => {
      const q = method ? `?skip=${skip}&limit=${limit}&method=${encodeURIComponent(method)}` : `?skip=${skip}&limit=${limit}`;
      return request(`/analytics/audit-logs${q}`);
    },
  },

  admin: {
    listUsers: async (skip = 0, limit = 50): Promise<{ total: number; items: User[] }> => {
      return request(`/admin/users?skip=${skip}&limit=${limit}`);
    },
    updateUser: async (userId: string, data: { role?: string; is_active?: boolean }): Promise<any> => {
      return request(`/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },
    getSystemConfig: async (): Promise<Record<string, any>> => {
      return request('/admin/system-config');
    },
  },

  health: {
    checkReady: async (): Promise<SystemHealth> => {
      const res = await fetch('/health/ready');
      return res.json();
    },
    checkLive: async (): Promise<{ status: string; app: string; environment: string; timestamp: string }> => {
      const res = await fetch('/health');
      return res.json();
    },
  },
};

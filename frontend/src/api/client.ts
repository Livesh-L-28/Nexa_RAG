import { ChatResponse, Citation, Document, RetrievalMetadata, User } from '../types';

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
      const errorJson = await response.json();
      if (errorJson?.error?.message) {
        errorMsg = errorJson.error.message;
      } else if (errorJson?.detail) {
        errorMsg = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Ignore JSON parse errors
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
    list: async (): Promise<{ total: number; items: Document[] }> => {
      return request('/documents');
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
    reprocess: async (id: string): Promise<any> => {
      return request(`/documents/${id}/process`, {
        method: 'POST',
      });
    },
  },

  chat: {
    listSessions: async () => {
      return request<any[]>('/chat/sessions');
    },
    getSession: async (sessionId: string) => {
      return request<any>(`/chat/sessions/${sessionId}`);
    },
    deleteSession: async (sessionId: string) => {
      return request<{ message: string }>(`/chat/sessions/${sessionId}`, {
        method: 'DELETE',
      });
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
      }
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

  health: {
    check: async () => {
      const res = await fetch('/health/ready');
      return res.json();
    },
  },
};

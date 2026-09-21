export interface User {
  id: string;
  email: string;
  role: 'USER' | 'ADMIN';
  is_active: boolean;
  created_at: string;
}

export interface Chunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  page_number?: number | null;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface Document {
  id: string;
  user_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  chunk_count: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  chunks?: Chunk[];
}

export interface Citation {
  document_id: string;
  filename: string;
  page_number?: number | null;
  chunk_index: number;
  content: string;
  relevance_score?: number | null;
}

export interface RetrievalMetadata {
  retrieval_method: string;
  candidates_count: number;
  top_k: number;
  reranking_enabled: boolean;
  retrieval_latency_ms: number;
  reranking_latency_ms: number;
  llm_latency_ms: number;
  total_latency_ms: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: Citation[];
  metadata?: RetrievalMetadata;
  created_at: string;
}

export interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
}

export interface ChatResponse {
  session_id: string;
  query: string;
  answer: string;
  sources: Citation[];
  retrieved_chunks: any[];
  metadata: RetrievalMetadata;
}

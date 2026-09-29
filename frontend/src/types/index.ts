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
  collection?: string;
}

export interface Citation {
  document_id: string;
  filename: string;
  page_number?: number | null;
  chunk_index: number;
  content: string;
  relevance_score?: number | null;
  retrieval_method?: string;
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

  // CAG
  cag_enabled?: boolean;
  cag_selected?: boolean;
  cache_hit?: boolean;
  cache_miss?: boolean;
  cache_context_count?: number;
  cache_context_size?: number;

  // MAG
  mag_enabled?: boolean;
  mag_selected?: boolean;
  memories_retrieved?: number;
  memories_used?: number;
  memory_retrieval_latency_ms?: number;
  memory_types?: string[];

  // Routing & Orchestration
  routing_enabled?: boolean;
  routing_latency_ms?: number;
  routing_confidence?: number;
  routing_reason?: string;
  selected_sources?: string[];
  provider_failures?: string[];

  // LLM Details & TTFT
  llm_provider?: string;
  llm_model?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  time_to_first_token_ms?: number | null;
  request_id?: string;
  prompt_build_latency_ms?: number;
  estimated_input_tokens?: number;
  dropped_contexts_count?: number;
  dropped_reasons?: Record<string, number>;

  // Guardrails
  guardrails_enabled?: boolean;
  guardrail_input_decision?: string;
  guardrail_retrieval_decision?: string;
  guardrail_output_decision?: string;
  guardrail_latency_ms?: number;
  guardrail_violations?: string[];
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
  request_id?: string;
}

export interface MemoryRecord {
  id: string;
  user_id: string;
  memory_type: string;
  content: string;
  importance: number;
  metadata: Record<string, any>;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryStats {
  total_memories: number;
  memories_by_type: Record<string, number>;
  last_updated?: string | null;
}

export interface CacheEntry {
  cache_id: string;
  namespace: string;
  key: string;
  content: string;
  version: number;
  created_at: string;
  updated_at: string;
  user_id?: string | null;
  metadata: Record<string, any>;
  expires_at?: string | null;
  priority: number;
}

export interface CacheStats {
  hits: number;
  misses: number;
  total_entries: number;
  hit_rate: number;
  size_bytes: number;
  last_refresh?: string | null;
}

export interface LatencyStat {
  count: number;
  min_ms?: number | null;
  max_ms?: number | null;
  avg_ms: number;
}

export interface TelemetrySummary {
  counters: Record<string, number>;
  cache_hit_rate: number;
  latencies: Record<string, LatencyStat>;
  errors_by_type: Record<string, number>;
  contexts_dropped_by_reason: Record<string, number>;
  recent_events_count: number;
}

export interface OverviewMetrics {
  documents: {
    total: number;
    status_breakdown: Record<string, number>;
    total_chunks: number;
  };
  chat: {
    total_sessions: number;
    total_messages: number;
    total_queries: number;
  };
  telemetry: TelemetrySummary;
  is_admin: boolean;
}

export interface AuditLog {
  id: string;
  user_id?: string | null;
  session_id?: string | null;
  request_id?: string | null;
  query: string;
  retrieval_method: string;
  candidate_count: number;
  top_k: number;
  reranking_enabled: boolean;
  retrieval_latency_ms: number;
  reranking_latency_ms: number;
  llm_latency_ms: number;
  total_latency_ms: number;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface Collection {
  id: string;
  name: string;
  description: string;
  document_ids: string[];
  created_at: string;
}

export interface SystemHealth {
  status: 'ready' | 'not_ready' | 'healthy' | 'degraded';
  database: string;
  vector_support: boolean;
  llm_provider: string;
  metrics?: TelemetrySummary;
  details?: Record<string, any>;
  timestamp: string;
}

export type NavigationTab =
  | 'overview'
  | 'chat'
  | 'documents'
  | 'collections'
  | 'inspector'
  | 'memory'
  | 'cache'
  | 'analytics'
  | 'security'
  | 'users'
  | 'system'
  | 'audit';

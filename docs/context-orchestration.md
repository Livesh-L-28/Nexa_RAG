# NexaRAG Context Orchestration Architecture

This document details the architectural foundation for Context Orchestration in NexaRAG, establishing the unified `ContextBundle` contract that links context sources (RAG, CAG, and MAG) to prompt synthesis and LLM providers.

---

## 1. Architectural Overview & Roadmap

```text
                                 User Query
                                     │
                                     ▼
                        Context Orchestration Layer
                                     │
               ┌─────────────────────┼─────────────────────┐
               ▼                     ▼                     ▼
          RAG Pipeline          CAG Provider          MAG Provider
      [IMPLEMENTED NOW]      [IMPLEMENTED NOW]     [IMPLEMENTED NOW]
               │                     │                     │
               │ (Scored Chunks)     │ (Cached Context)    │ (Memories)
               │                     │                     │
               └─────────────────────┼─────────────────────┘
                                     │
                                     ▼
                               Context Fusion
                             [IMPLEMENTED NOW]
                                     │
                                     ▼
                               ContextBundle
                             [IMPLEMENTED NOW]
                                     │
                                     ▼
                               Prompt Builder
                             [IMPLEMENTED NOW]
                                     │
                                     ▼
                                LLM Provider
                      (Groq / Gemini / Mock LLM)
                             [IMPLEMENTED NOW]
```

### Component Implementation Status

| Component | Status | Description |
| :--- | :--- | :--- |
| **RAG Pipeline** | **IMPLEMENTED NOW** | Dense pgvector + BM25 hybrid retrieval, Cross-Encoder reranking |
| **ContextBundle** | **IMPLEMENTED NOW** | Provider-agnostic, typed Pydantic contract for unified context |
| **Context Priorities** | **IMPLEMENTED NOW** | Deterministic hierarchy: System > Security > RAG > CAG > MAG > History > Query |
| **Context Fusion** | **IMPLEMENTED NOW** | Deterministic assembly and metadata calculation |
| **RAG Context Adapter** | **IMPLEMENTED NOW** | Bridges retrieved document chunks and conversation history into ContextBundle |
| **Prompt Builder Integration** | **IMPLEMENTED NOW** | Builds grounded prompt directly from ContextBundle |
| **LLM Provider Hardening (Phase 12)** | **IMPLEMENTED NOW** | Unified generation contract, error normalization, retry policy, streaming safety, and token observability |
| **Observability & Metrics (Phase 13)** | **IMPLEMENTED NOW** | Monotonic timing, structured JSON event logging, concurrency-safe metrics recorder, streaming TTFT, and database correlation |
| **CAG Provider (Phase 8)** | **IMPLEMENTED NOW** | Cache-Augmented Generation with local storage, versioning, and deterministic policy |
| **MAG Provider (Phase 9)** | **IMPLEMENTED NOW** | Memory-Augmented Generation with PostgreSQL storage, selective extraction, and ranking |
| **Intelligent Context Orchestrator (Phase 10)** | **IMPLEMENTED NOW** | Deterministic-first query signal analysis, ContextPlan generation, and concurrent multi-source selection |
| **Context Fusion Hardening (Phase 11)** | **IMPLEMENTED NOW** | Production-hardened normalization, deduplication, deterministic tie-breaking, token budgeting, and dropped-context tracking |

---

## 2. Current Flow vs Context Orchestration Flow

### Existing Flow (Baseline)
1. **HTTP Request**: User sends query to `/api/v1/chat` or `/api/v1/chat/stream`.
2. **Chat Route**: Authenticates user via JWT, validates session ownership, retrieves last 10 messages from DB.
3. **Query Expansion**: Rewrites query with historical conversational context (`QueryProcessor.rewrite_with_history`).
4. **Hybrid Retrieval**: Combines pgvector cosine similarity search and rank-bm25 lexical scoring.
5. **Cross-Encoder Reranker**: Reranks top candidates using cross-encoder model.
6. **Context Builder**: Formats `ScoredChunk` instances into text blocks with `[Source X]` markers and builds `Citation` list.
7. **Prompt Builder**: Injects formatted context, conversation history, and query into system/user prompts.
8. **LLM Provider**: `BaseLLM.generate` or `BaseLLM.generate_stream` executes generation via Groq, Gemini, or Mock.
9. **Persistence & Response**: Saves assistant message with citations, writes observability log to DB, returns response.

### Context Orchestration Flow (Phase 0, Phase 8, & Phase 9)
RAG, CAG, and MAG act additively:
```text
Hybrid Retrieval (RAG)   +   CAG Lookup (CachedContext)   +   MAG Retrieval (MemoryContext)
           \                             |                            /
            \                            |                           /
             ▼                           ▼                          ▼
      RAGContextAdapter          CAGContextProvider          MAGContextProvider
                     \                   |                   /
                      \                  |                  /
                       ▼                 ▼                 ▼
                                DefaultContextFusion
                                         │
                                         ▼
                                   ContextBundle
                                         │
                                         ▼
                            PromptBuilder (Grounded Prompt)
                                         │
                                         ▼
                                    LLM Provider
```

---

## 3. Current Context & Prompt Representation

### Context Builder (`app/rag/context_builder.py`)
- Input: `list[ScoredChunk]`
- Output: `BuiltContext(formatted_context: str, citations: list[Citation], chunk_ids: list[UUID])`
- Formats document excerpts into structured blocks with `[Source X]` markers.

### Prompt Builder (`app/rag/prompt_builder.py`)
- `build_system_prompt()`: Defines enterprise assistant role, strict grounding rules, mandatory `[Source X]` citations, and lack-of-information handling.
- `build_user_prompt()` / `build_user_prompt_from_bundle()`: Assembles conversation history, document context (RAG), cached knowledge context (CAG), relevant user memories (MAG), and user question.

---

## 4. LLM Provider Abstraction

NexaRAG isolates all LLM calls in `app/llm/`:
- `BaseLLM`: Abstract base class with `generate(...)` and `generate_stream(...)`.
- `GroqLLM`, `GeminiLLM`, `MockLLM`: Concrete implementations selected via `LLM_PROVIDER` environment variable.
- The orchestration layer never makes direct vendor API calls.

---

## 5. Context Priorities

To prevent untrusted or low-priority context from overriding system constraints, context injection respects strict priority ordering:

1. **System Instructions** (`SYSTEM = 1`): Base assistant instructions and core grounding rules.
2. **Security Constraints** (`SECURITY = 2`): Tenant isolation, authorization, and safety guards.
3. **Authoritative Documents (RAG)** (`RAG = 3`): Ground-truth factual knowledge retrieved from enterprise documents.
4. **Cached Knowledge (CAG)** (`CAG = 4`): Pre-computed or warm cached knowledge contexts (*Phase 8*).
5. **User Memories (MAG)** (`MAG = 5`): User preferences, past episodic interactions, or profile state (*Phase 9*).
6. **Conversation History** (`CONVERSATION = 6`): Recent multi-turn dialogue turns.
7. **User Question** (`QUERY = 7`): Current user prompt.

---

## 6. Phase 8 — Cache-Augmented Generation (CAG)

### 6.1 What CAG Is
Cache-Augmented Generation (CAG) allows NexaRAG to store and retrieve pre-processed, frequently referenced, or stable domain knowledge, injecting it directly into the `ContextBundle` alongside retrieved document chunks.

### 6.2 Why NexaRAG Uses CAG
- **Retrieval Bypass for Stable Domains**: Reduces embedding, vector search, and cross-encoder compute for repetitive reference knowledge.
- **Additive Grounding**: Enriches RAG with standard organizational policies, guidelines, and reference schemas.
- **Predictable Latency**: Local cache lookups execute in sub-millisecond time.

### 6.3 What Is Cached vs What Is Not Cached
- **Cached**: Stable policies, handbooks, architecture standards, compliance guidelines, static system documentation, and explicitly registered domain reference material.
- **NOT Cached**: Arbitrary volatile conversational turns, private secrets/credentials, untrusted arbitrary user text, rapidly changing transactional database records, or unvetted data.

### 6.4 Cache Lifecycle & Versioning
- **Key Design**: Deterministic namespaced keys formatted as `namespace:identifier` (or `namespace:user_id:identifier` for user-specific cache).
- **Versioning**: Every cache entry begins at `version = 1`. Updating an entry via `refresh_context` atomically increments `version` and updates `updated_at`.
- **Invalidation**: Entries can be invalidated on demand by key or namespace via `invalidate_context`.

### 6.5 Cache Hit / Miss Behavior
- **Hit**: The entry is loaded, validated against expiration and user boundaries, and converted to `CachedContext`.
- **Miss**: Recorded in `CacheStats` and `RetrievalMetadata`. When CAG misses or has no eligible domains, the pipeline seamlessly continues with pure RAG.

### 6.6 Context Size Control
To prevent prompt token blowup, CAG enforces a configurable `max_context_chars` limit (default: 4,000 characters). Overflowing content is cleanly truncated with a marker.

### 6.7 User Isolation
- **Global Entries (`user_id = None`)**: Available to all authorized queries matching the domain policy.
- **User-Specific Entries (`user_id = UUID`)**: Enforced at the `CacheStore` layer. User A cannot view, retrieve, overwrite, or delete User B's cache entries.

---

## 7. Phase 9 — Memory-Augmented Generation (MAG)

### 7.1 What MAG Is [IMPLEMENTED]
Memory-Augmented Generation (MAG) enables NexaRAG to selectively extract, persist, and retrieve relevant long-term user memories (preferences, project facts, guidelines, instructions) across sessions, without treating raw chat turns as permanent memories. It operates additively alongside RAG and CAG within the unified `ContextBundle`.

### 7.2 Why NexaRAG Needs Memory [IMPLEMENTED]
- **Persistent Personalization**: Retains persistent user preferences (e.g., programming language, response formatting, tone) across multiple disparate sessions.
- **Project Context Retention**: Maintains architecture facts, tech stacks, and environment details for ongoing projects across sessions without re-prompting.
- **Differentiating History from Memory**: Conversation history (`ChatSession`/`ChatMessage`) stores immediate multi-turn context (short-term buffer); long-term memory (`MemoryStore`) selectively persists validated, durable facts.

### 7.3 Memory Types [IMPLEMENTED]
NexaRAG classifies memories into typed categories via the `MemoryType` enum:
- `preference`: Explicit user preferences (e.g., "User prefers Python over Java").
- `profile`: User role, specialization, or background (e.g., "User is an AI systems engineer").
- `project_context`: Active project stack and architecture (e.g., "User is building a FastAPI backend with PostgreSQL").
- `conversation_fact`: Verified historical decisions or milestones (e.g., "User previously deployed the project with Docker").
- `instruction`: Durable user interaction rules (e.g., "Always provide concise explanations in bullet points").
- `temporary_context`: Transient focal points with explicit expiration timestamps (e.g., "User is currently debugging the authentication module").

### 7.4 Memory Lifecycle & Conflict Resolution [IMPLEMENTED]
1. **Extraction**: `MemoryExtractor` parses user input using deterministic heuristics.
2. **Validation**: Checks for minimum importance and runs security credential filtering.
3. **Conflict Resolution**: When an incoming memory addresses an existing topic (e.g., "User prefers Python" replacing an earlier "User prefers Java"), `MemoryManager` updates the existing record in-place with the new content and refreshed `updated_at`, preventing stale contradictions.
4. **Persistence**: Stored in PostgreSQL with SQLAlchemy via `MemoryStore`.
5. **Retrieval**: Queried and ranked upon subsequent user questions.
6. **Expiration**: Ephemeral memories past `expires_at` are excluded from active retrieval.

### 7.5 Extraction Strategy & Decision Process [IMPLEMENTED]
- **Deterministic & Lightweight**: Uses rule-based regex patterns rather than requiring an expensive LLM call for extraction.
- **Heuristic Triggers**: Captures explicit directives ("Remember that...", "Please remember..."), behavioral constraints ("Always format...", "Never use..."), personal preferences ("I prefer..."), and project facts ("I am building...", "Our stack uses...").
- **Trivial Phrase Filtering**: Discards conversational filler ("ok", "thanks", "hello", "understood", "yes", "sure").
- **Secret Filtering**: Immediately halts extraction if any sensitive token is detected.

### 7.6 Importance Scoring [IMPLEMENTED]
Each memory is assigned a float importance score in $[0.0, 1.0]$:
- **0.90 – 1.00**: Explicit user instructions (`"Remember that..."` = 0.95, `"Always explain..."` = 0.90).
- **0.70 – 0.89**: High-value project stack and preferences (`0.85`).
- **0.50 – 0.69**: Ephemeral/temporary focus (`0.60`).
- **< 0.50**: Discarded; not persisted.

### 7.7 Multi-Signal Retrieval & Top-K Limit [IMPLEMENTED]
Memories are retrieved and ranked using a multi-signal scoring function:
$$\text{Score} = (0.60 \times \text{Relevance}) + (0.25 \times \text{Importance}) + (0.15 \times \text{Recency})$$
- **Lexical Relevance ($0.60$)**: Alphanumeric token intersection between query and memory content (stopwords removed). Instructions receive a 0.40 baseline relevance. Memories with zero relevance are excluded.
- **Importance ($0.25$)**: Stored importance score $[0.0, 1.0]$.
- **Recency ($0.15$)**: Linear decay over a 30-day window based on `updated_at` (floored at $0.10$).
- **Top-K Limit**: Enforces a configurable `MEMORY_TOP_K` (default: 5) to prevent context window bloat.

### 7.8 Memory Expiration [IMPLEMENTED]
- Memories support an optional `expires_at` timestamp.
- Primarily used for `temporary_context` (default TTL: 7 days).
- Long-term preferences and project facts have `expires_at = NULL` (indefinite).
- Query filtering excludes all expired memories at both database query and retriever levels (`Memory.expires_at.is_(None) | Memory.expires_at > now`).

### 7.9 User Isolation [IMPLEMENTED]
- **Tenant Boundary**: Every entry in the `memories` table requires a mandatory non-null `user_id` foreign key referencing `users.id` with `CASCADE` delete.
- **Service & Repository Layer Enforcement**: Every database query (`get_memory`, `update_memory`, `delete_memory`, `list_memories`, `retrieve`) strictly filters by `user_id == current_user.id`.
- User A can never read, update, list, or delete User B's memories under any condition.

### 7.10 ContextBundle & Priority Integration [IMPLEMENTED]
- `MAGContextProvider` implements the provider-agnostic `ContextProvider` interface.
- Retrieved memories are converted into `MemoryContext` objects.
- Integrated into `ContextBundle` via `DefaultContextFusion`.
- Respects strict priority hierarchy:
  $$\text{System} > \text{Security} > \text{RAG} > \text{CAG} > \text{MAG} > \text{Conversation} > \text{Query}$$
- User memories provide personalization context and cannot override authoritative system constraints or enterprise document facts.

### 7.11 Security & Secret Filtering [IMPLEMENTED]
- `MemoryExtractor.contains_secret()` inspects candidate text against regex patterns for:
  - OpenAI / generic API keys (`sk-...`)
  - GitHub personal access tokens (`ghp_...`)
  - Bearer tokens and JWTs (`Bearer ...`, `eyJ...`)
  - RSA/EC private keys (`-----BEGIN PRIVATE KEY-----`)
  - Password declarations (`password = ...`, `secret: ...`)
  - Database connection URIs containing credentials (`postgres://user:pass@...`)
- Messages matching any secret pattern are rejected from memory extraction.

### 7.12 Current Limitations [IMPLEMENTED]
- Extraction relies on deterministic pattern matching rather than semantic parsing.
- Retrieval relies on token overlap, importance weighting, and recency decay rather than semantic vector embeddings.
- In-memory SQLite test environment uses UTC-normalized naive datetimes, while production runs PostgreSQL with `TIMESTAMP WITH TIME ZONE`.

### 7.13 Future Extensions [FUTURE]
- **Embedding-Based Memory Retrieval (Phase 11+)**: Generate vector embeddings for memories using `pgvector` for semantic similarity retrieval.
- **Memory Consolidation & Summarization**: Periodic background consolidation of recurring episodic memories into structured user profiles.

---

## 8. Phase 10 — Intelligent Context Orchestrator [IMPLEMENTED NOW]

### 8.1 Overview & Architecture
The Context Orchestrator provides a deterministic-first routing layer that determines **which context sources should participate in answering a query** (`RAG`, `CAG`, `MAG`, `Conversation`) before retrieval begins.

The orchestrator adheres to a strict separation of concerns:
- **Orchestrator**: Decides *WHAT* context is needed.
- **Underlying Providers (RAG, CAG, MAG)**: Decide *HOW* retrieval and ranking are executed.

```text
                                  User Query
                                      │
                                      ▼
                           RuleBasedQueryAnalyzer
                                      │ (QuerySignals)
                                      ▼
                            RuleBasedContextPolicy
                                      │ (ContextPlan)
                                      ▼
                             ContextOrchestrator
                                      │
              ┌───────────────────────┼───────────────────────┐
              │ (if RAG in Plan)      │ (if CAG in Plan)      │ (if MAG in Plan)
              ▼                       ▼                       ▼
      RAGContextProvider      CAGContextProvider      MAGContextProvider
              │                       │                       │
              └───────────────────────┼───────────────────────┘
                                      │ (asyncio.gather with failure isolation)
                                      ▼
                                ContextFusion
                                      │
                                      ▼
                                ContextBundle
                                      │
                                      ▼
                                 Prompt / LLM
```

### 8.2 ContextDecision & ContextPlan Models
Defined in [backend/app/orchestration/models.py](file:///Users/livesh/NexaRAG/backend/app/orchestration/models.py):

* **`ContextDecision`**:
  - `source`: `ContextSource` (`RAG`, `CAG`, `MAG`, `CONVERSATION`, `SYSTEM`, `SECURITY`)
  - `enabled`: `bool` (whether this source is selected)
  - `confidence`: `float` ($0.0$ to $1.0$, routing confidence score)
  - `reason`: `str` (human-readable explanation for debugging and observability)
* **`ContextPlan`**:
  - `decisions`: `list[ContextDecision]`
  - `routing_latency_ms`: `float` (latency spent in analyzer + policy)
  - `routing_confidence`: `float` (overall confidence)
  - `routing_reason`: `str` (summary rationale for routing plan)
  - `selected_sources`: property returning `list[ContextSource]` containing all sources where `enabled is True`

### 8.3 Query Signal Extraction Rules
Defined in [backend/app/orchestration/analyzer.py](file:///Users/livesh/NexaRAG/backend/app/orchestration/analyzer.py) via `RuleBasedQueryAnalyzer`:

| Signal | Detection Rule / Triggers | Example Matches |
| :--- | :--- | :--- |
| `is_chitchat` | Short greeting/farewell/gratitude regex ($\le 6$ words) | `"hello"`, `"hi there"`, `"thanks!"`, `"goodbye"` |
| `has_memory_ref` | Recall keywords or user preference pronouns | `"remember"`, `"my preference"`, `"what did I tell you"` |
| `has_doc_ref` | Document, search, or retrieval keywords | `"search the docs"`, `"in the manual"`, `"documentation"` |
| `has_policy_ref` | Organization, architecture, or policy keywords | `"architecture"`, `"coding standards"`, `"leave policy"` |
| `has_project_ref` | Project-specific phrasing or terminology | `"in our project"`, `"NexaRAG implementation"`, `"codebase"` |
| `has_conv_ref` | Anaphoric or conversational references | `"what did you just say"`, `"earlier you mentioned"` |
| `has_user_ref` | First-person singular references | `"my settings"`, `"for me"`, `"I prefer"` |

### 8.4 Decision Rules Matrix
Defined in [backend/app/orchestration/policies.py](file:///Users/livesh/NexaRAG/backend/app/orchestration/policies.py) via `RuleBasedContextPolicy`:

| Query Intent / Detected Signals | Sources Enabled | Confidence | Reason |
| :--- | :--- | :--- | :--- |
| Pure chit-chat (`is_chitchat`) | `Conversation` only | 0.95 | Casual conversation detected; context retrieval bypassed |
| Explicit memory query (`has_memory_ref` without docs/policies) | `MAG` + `Conversation` | 0.90 | Personal memory reference detected |
| General knowledge / default fallback | `RAG` + `Conversation` | 0.75 | Default retrieval path for knowledge queries |
| Architecture / Policy reference (`has_policy_ref` without memory) | `CAG` + `Conversation` | 0.90 | System architectural context requested |
| Document + Memory query (`has_doc_ref` and `has_memory_ref`) | `RAG` + `MAG` + `Conversation` | 0.85 | Dual retrieval: document knowledge and user memory |
| Policy + Memory query (`has_policy_ref` and `has_memory_ref`) | `CAG` + `MAG` + `Conversation` | 0.85 | Dual retrieval: architectural context and user memory |
| All-domain query (all signals present) | `RAG` + `CAG` + `MAG` + `Conversation` | 0.90 | Comprehensive multi-source retrieval required |

### 8.5 Concurrency and Failure Isolation Model
Context retrieval runs concurrently using `asyncio.gather(..., return_exceptions=True)` in `ContextOrchestrator.execute_plan`:

1. **Concurrent Execution**:
   - `RAG`, `CAG`, and `MAG` queries are dispatched simultaneously as async tasks.
   - Total retrieval time is bounded by $\max(T_{\text{rag}}, T_{\text{cag}}, T_{\text{mag}})$ rather than $T_{\text{rag}} + T_{\text{cag}} + T_{\text{mag}}$.
2. **Failure Isolation (Graceful Degradation)**:
   - If a provider encounters an internal error (e.g. database timeout or corrupt chunk index), the exception is captured.
   - The failing provider is recorded in `metadata.provider_failures` (e.g., `["mag: database connection timeout"]`).
   - The remaining successful providers proceed unimpeded into `ContextFusion`.
   - **Critical Exception Preservation**: Authentication errors (`HTTPException` with 401/403), tenant isolation violations, or cancellation exceptions are re-raised immediately and never silently swallowed.

### 8.6 Observability and Metadata Schema
Extended `RetrievalMetadata` schema in [backend/app/schemas/chat.py](file:///Users/livesh/NexaRAG/backend/app/schemas/chat.py):

```python
class RetrievalMetadata(BaseModel):
    # Core RAG metrics
    sources: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0

    # Source selection indicators
    rag_selected: bool = False
    cag_selected: bool = False
    mag_selected: bool = False

    # Orchestration observability
    routing_enabled: bool = False
    routing_latency_ms: float = 0.0
    routing_confidence: float = 1.0
    routing_reason: str | None = None
    selected_sources: list[str] = Field(default_factory=list)
    provider_failures: list[str] = Field(default_factory=list)
```

### 8.7 Backward Compatibility & Test Guardrails
- `RAGPipeline(routing_enabled=False)` is preserved by default for backwards compatibility with earlier unit tests.
- Production API dependency `get_rag_pipeline()` initializes `RAGPipeline(routing_enabled=True)`.
- Existing `/chat` requests continue to receive valid responses regardless of whether routing is toggled.
- Additive fusion priorities are maintained strictly:
  $$\text{System} > \text{Security} > \text{RAG} > \text{CAG} > \text{MAG} > \text{Conversation} > \text{Query}$$

### 8.8 Current Limitations & Future Extensions
- **Current Limitations**:
  - Signal extraction uses deterministic regex and token matching; subtle semantic nuances may fall back to default RAG.
  - Confidence scores are rule-based heuristics rather than probabilistic model calibrations.
- **Future Roadmap (Phase 12+)**:
  - **Lightweight Embedding / LLM Intent Classifier**: Fine-tuned Small Language Model (SLM) or embedding router for semantic intent classification with ambiguous phrasing.
  - **Adaptive Dynamic Routing**: Query performance feedback loop adjusting source thresholds based on answer quality and user ratings.

---

## 9. Phase 11 — Context Fusion Hardening [IMPLEMENTED NOW]

### 9.1 Overview & Responsibilities [IMPLEMENTED]
The Context Fusion layer (`DefaultContextFusion` in [backend/app/orchestration/fusion.py](file:///Users/livesh/NexaRAG/backend/app/orchestration/fusion.py)) deterministically combines multiple context streams into a single, unified `ContextBundle`.

**Fusion Responsibilities**:
- Accept context streams: `RAGContext`, `CachedContext`, `MemoryContext`, and `ConversationContext`.
- Normalize all incoming items into `NormalizedContext`.
- Deduplicate content across sources using normalized content hashing, where higher-priority sources win.
- Apply relevance score thresholds (`min_context_score`) to scored items.
- Order deterministically: `priority (asc) -> relevance score (desc) -> source_id (asc)`.
- Enforce token budgets (both global `max_context_tokens` and source-specific budgets) with complete item selection (no mid-item truncation).
- Validate tenant/user isolation boundaries on user-specific context.
- Track dropped context reasons (`DroppedContext`) for full observability.

**What Fusion Does NOT Do**:
- ❌ No vector search or BM25 retrieval.
- ❌ No cross-encoder reranking.
- ❌ No database or SQL execution.
- ❌ No embedding generation.
- ❌ No LLM calls (Gemini/Groq/Mock).
- ❌ No LLM query routing.

```text
                    Context Sources (RAG, CAG, MAG, Conversation)
                                         │
                                         ▼
                                 Context Collector
                                         │
                                         ▼
                               Context Normalization
                                (NormalizedContext)
                                         │
                                         ▼
                               Content Deduplication
                        (Intra & Cross-source, priority wins)
                                         │
                                         ▼
                                Relevance Filtering
                            (Score threshold filtering)
                                         │
                                         ▼
                         Deterministic Priority Ordering
                     (Priority asc -> Score desc -> Source_ID asc)
                                         │
                                         ▼
                              Priority-Aware Budgeting
                         (Global & source budgets, complete items)
                                         │
                                         ▼
                                Security Validation
                         (Verify user_id/owner_id isolation)
                                         │
                                         ▼
                                   ContextBundle
                                         │
                                         ▼
                                   PromptBuilder
```

### 9.2 Context Normalization [IMPLEMENTED]
All provider contexts are converted into a unified internal model `NormalizedContext`:
- `source`: `ContextSource` (`RAG`, `CAG`, `MAG`, `CONVERSATION`)
- `content`: `str` (unmodified raw text)
- `priority`: `int` (`ContextPriority` integer value)
- `score`: `float | None` (retrieval/relevance score, or `turn_index` for conversation)
- `source_id`: `str` (`chunk_id`, `cache_id`, `memory_id`, or `conv_turn_id`)
- `metadata`: `dict[str, Any]` (source-specific attributes)
- `estimated_tokens`: `int` (approximated tokens)
- `original_item`: `Any` (unmodified original typed model instance)

### 9.3 Priority Ordering & Tie-Breaking [IMPLEMENTED]
Strict precedence hierarchy is preserved:
$$\text{SYSTEM (1)} > \text{SECURITY (2)} > \text{RAG (3)} > \text{CAG (4)} > \text{MAG (5)} > \text{CONVERSATION (6)} > \text{QUERY (7)}$$
- *Lower number = higher priority.*
- Deterministic tie-breaking key:
  $$\text{sort\_key}(c) = (\text{priority}, -\text{score}, \text{source\_id})$$
- RAG chunks are consistently ordered by relevance score descending.
- Conversation history ranks recent turns before older turns during budgeting, and preserves chronological sequence in final prompt output.

### 9.4 Deduplication (Intra-Source and Cross-Source) [IMPLEMENTED]
- Content comparison uses normalized keys (trimmed, whitespace collapsed, lowercase comparison) without altering the original text.
- Cross-source collisions:
  - If identical content appears in RAG and MAG: **RAG wins** (priority 3 < priority 5).
  - If identical content appears in RAG and CAG: **RAG wins** (priority 3 < priority 4).
  - If identical content appears in CAG and MAG: **CAG wins** (priority 4 < priority 5).
  - If identical content appears in MAG and Conversation: **MAG wins** (priority 5 < priority 6).
- Intra-source collisions: higher relevance score wins; on equal score, smaller `source_id` tie-breaker wins.
- Dropped items are logged in `ContextMetadata.dropped_contexts` with reason `"duplicate"`.

### 9.5 Source Attribution Preservation [IMPLEMENTED]
Source attribution is 100% preserved through `original_item` reference:
- **RAG**: Retains `document_id`, `chunk_id`, `filename`, `page_number`, `chunk_index`, `score`, and `metadata`.
- **CAG**: Retains `cache_id`, `version`, and `metadata`.
- **MAG**: Retains `memory_id`, `memory_type`, `importance`, `relevance_score`, and `metadata`.
- **Conversation**: Retains `session_id`, `role`, `content`, and `created_at`.

### 9.6 Token Estimation [IMPLEMENTED]
- Implemented in `TokenEstimator.estimate(text: str) -> int`.
- Deterministic rule: `max(1, ceil(len(text) / 4.0))`.
- Fast, CPU-friendly, zero external dependencies.

### 9.7 Token Budgeting [IMPLEMENTED]
Defined in `ContextBudgetConfig`:
- `max_context_tokens`: Global ceiling (default: 6000).
- `max_rag_tokens`: RAG sub-budget (default: 4000).
- `max_cag_tokens`: CAG sub-budget (default: 1500).
- `max_mag_tokens`: MAG sub-budget (default: 1000).
- `max_conversation_tokens`: Conversation sub-budget (default: 1000).
- **Hard rule**: Global budget strictly overrides source sub-budgets.
- **Complete item selection**: Context items are never cut in half; an item is included entirely or excluded.

### 9.8 Relevance Filtering [IMPLEMENTED]
- Configured via `min_context_score` (default: `None` / `0.0`).
- If set, scored items with `score < min_context_score` are excluded with reason `"below_relevance_threshold"`.
- Unscored items (such as CAG and Conversation) are not dropped by score filters.

### 9.9 Conflict Precedence & Prompt Safety [IMPLEMENTED]
- Authoritative document context (`RAG`) always overrides cached policy (`CAG`) and user memory (`MAG`).
- User memory is contextual personalization, not authoritative truth.
- All fused contexts remain data blocks under distinct section headers (`DOCUMENT CONTEXT`, `CACHED KNOWLEDGE CONTEXT`, `RELEVANT USER MEMORY CONTEXT`, `CONVERSATION HISTORY`). No context is ever promoted into system instructions.

### 9.10 Security & User Isolation Validation [IMPLEMENTED]
- `DefaultContextFusion.fuse` accepts `current_user_id`.
- If user-scoped metadata (`user_id` or `owner_id`) is present on any item and does not match `current_user_id`, the item is dropped with reason `"security_user_mismatch"`.

### 9.11 Dropped-Context Tracking [IMPLEMENTED]
Every excluded item is recorded in `ContextMetadata.dropped_contexts` using `DroppedContext`:
- `source`: ContextSource
- `source_id`: str
- `reason`: `"duplicate"`, `"below_relevance_threshold"`, `"source_token_budget"`, `"token_budget"`, `"security_user_mismatch"`, `"invalid"`
- `priority`: int
- `score`: float | None
- `estimated_tokens`: int

### 9.12 Current Limitations [IMPLEMENTED]
- Token estimation uses character-based approximation ($4\text{ chars} \approx 1\text{ token}$) rather than exact BPE tokenization.
- Deduplication relies on normalized token sequence matching rather than semantic embedding similarity.

### 9.13 Future Extensions [FUTURE]
- **Exact Tokenizer Integration (Phase 13+)**: Pluggable `tiktoken` or Hugging Face `tokenizers` backend for exact token accounting across heterogeneous LLM providers.
- **Semantic Deduplication**: Near-duplicate clustering based on cosine similarity thresholds.

---

## 10. Phase 12 — LLM Provider Integration Hardening [IMPLEMENTED NOW]

### 10.1 Overview & Provider Abstraction [IMPLEMENTED]
Phase 12 hardens the final synthesis layer linking the fused `ContextBundle` and `PromptBuilder` to LLM providers.

```text
                                ContextBundle
                                      │
                                      ▼
                                PromptBuilder
                        (Grounded prompt synthesis)
                                      │
                                      ▼
                                 LLMProvider
                          (BaseLLM unified contract)
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                     GeminiLLM     GroqLLM      MockLLM
                    (REST API)   (Chat Comp)   (Local CI)
                         │            │            │
                         └────────────┼────────────┘
                                      │
                              (Error Normalizer)
                        ProviderAuthenticationError
                        ProviderRateLimitError
                        ProviderTimeoutError
                        ProviderUnavailableError
                        ProviderGenerationError
                                      │
                         (Controlled Transient Retry)
                                      │
                                      ▼
                                 LLMResponse
                   (text, provider, model, usage, latency)
```

- **Strict Separation**: The pipeline and orchestration layer never branch on provider names (`if provider == "gemini"`). All provider interactions use the `BaseLLM` interface defined in [backend/app/llm/base.py](file:///Users/livesh/NexaRAG/backend/app/llm/base.py).
- **Core Interfaces**:
  - `generate(prompt, system_prompt=None, config=None, **kwargs) -> str`: Standard text generation.
  - `generate_response(prompt, system_prompt=None, config=None, **kwargs) -> LLMResponse`: Returns normalized response container with full metadata.
  - `generate_stream(prompt, system_prompt=None, config=None, **kwargs) -> AsyncIterator[str]`: Progressive chunk generation.

### 10.2 Provider Factory & Lazy Initialization [IMPLEMENTED]
Implemented in [backend/app/llm/factory.py](file:///Users/livesh/NexaRAG/backend/app/llm/factory.py):
- `get_llm(provider=None, require_keys=False, **kwargs) -> BaseLLM`:
  - Validates provider name against allowed choices: `"gemini"`, `"groq"`, `"mock"`.
  - Raises `ValueError` on unsupported provider names.
  - **Lazy Initialization**: No network calls, client pings, or connections occur during application startup. Clients are created on demand.
  - **Offline Safety**: When live API keys are not configured, safely defaults to `MockLLM` unless `require_keys=True`.

### 10.3 Configuration Contracts [IMPLEMENTED]
- **`GenerationConfig`** in [backend/app/llm/models.py](file:///Users/livesh/NexaRAG/backend/app/llm/models.py):
  - `temperature: float = 0.2` ($0.0 \le t \le 2.0$)
  - `max_output_tokens: int = 1024` ($1 \le m \le 8192$)
  - `top_p: float | None = None` ($0.0 \le p \le 1.0$)
- **Environment Settings** in [backend/app/core/config.py](file:///Users/livesh/NexaRAG/backend/app/core/config.py):
  - `LLM_PROVIDER`: `"mock"`, `"gemini"`, or `"groq"`
  - `LLM_TIMEOUT_SECONDS`: `60.0`
  - `LLM_MAX_RETRIES`: `2`
  - `GEMINI_API_KEY`, `GROQ_API_KEY`, `GEMINI_MODEL`, `GROQ_MODEL`

### 10.4 Error Normalization [IMPLEMENTED]
All provider-specific HTTP and library exceptions are normalized in [backend/app/llm/exceptions.py](file:///Users/livesh/NexaRAG/backend/app/llm/exceptions.py):

| Exception | HTTP Status | Trigger Conditions |
| :--- | :---: | :--- |
| `ProviderAuthenticationError` | 401 | Missing, invalid, or unauthorized API key (401, 403) |
| `ProviderRateLimitError` | 429 | Rate limit or quota exceeded (429), records `retry_after` if available |
| `ProviderTimeoutError` | 504 | Request timeout, gateway timeout (504) |
| `ProviderUnavailableError` | 503 | Service unavailable, overloaded, or network drop (503) |
| `ProviderGenerationError` | 502 | Malformed JSON or decoding failures (502) |

### 10.5 Controlled Retry & Timeout Policy [IMPLEMENTED]
Implemented in [backend/app/llm/retry.py](file:///Users/livesh/NexaRAG/backend/app/llm/retry.py) via `execute_with_retry`:
- **Timeout**: Every external call enforces bounded timeout (`LLM_TIMEOUT_SECONDS = 60.0`).
- **Transient Failures Only**: Retries only `ProviderTimeoutError`, `ProviderUnavailableError`, `httpx.TimeoutException`, and `httpx.ConnectError`.
- **Non-Retryable Exceptions**: Fatal errors (`ProviderAuthenticationError`, `ProviderRateLimitError`, client errors) are **never** retried.
- **Exponential Backoff**: Up to 2 retries with delay: $\text{delay} = \min(3.0, 0.5 \times 2^{\text{attempt}-1})$.

### 10.6 Streaming Safety [IMPLEMENTED]
- **Clean Token Chunks**: Emits SSE data tokens progressively:
  `data: {"type": "token", "content": "..."}`
- **Mid-Stream Error Handling**: If a provider fails mid-stream, catches `ProviderError`, sanitizes the error message, and yields a structured error event:
  `data: {"type": "error", "message": "[PROVIDER] clean error"}`
  before cleanly terminating the stream.
- **No Tracebacks**: No Python tracebacks, credentials, or internal details leak over the SSE connection.

### 10.7 Mock Provider [IMPLEMENTED]
- Implemented in [backend/app/llm/mock.py](file:///Users/livesh/NexaRAG/backend/app/llm/mock.py):
- Deterministic, offline, zero network dependencies.
- Simulates realistic grounded responses and citations based on `[Source X]` in prompt.
- Reports calculated token usage statistics (`LLMUsage`).
- Test simulation hooks (`simulated_error="auth"`, `"rate_limit"`, `"timeout"`, `"unavailable"`).

### 10.8 Observability & Token Usage [IMPLEMENTED]
- **`LLMUsage`**: Captures `input_tokens`, `output_tokens`, and `total_tokens`.
- **`LLMResponse`**: Reports `provider`, `model`, `usage`, `finish_reason`, and `latency_ms`.
- **Extended `RetrievalMetadata`**:
  - `llm_provider: str`
  - `llm_model: str`
  - `input_tokens: int | None`
  - `output_tokens: int | None`
  - `total_tokens: int | None`
  - `time_to_first_token_ms: float | None`

### 10.9 Security & Secret Sanitization [IMPLEMENTED]
- Implemented in `sanitize_error_message()`:
  - Redacts query parameters: `key=AIza...` ➔ `key=[REDACTED]`
  - Redacts authorization headers: `Bearer ...` or `gsk_...` ➔ `[REDACTED_TOKEN]`
  - Redacts private key declarations: `sk-...` ➔ `[REDACTED_KEY]`
- API keys are never stored in `ContextBundle`, logs, database records, or returned over API endpoints.

### 10.10 Current Limitations [IMPLEMENTED]
- Provider selection is set globally via `LLM_PROVIDER` environment variable rather than per-request routing.
- Fallback between heterogeneous providers (e.g. Gemini ➔ Groq) is not automatic in Phase 12.

### 10.11 Future Extensions [FUTURE]
- **Automatic Cross-Provider Failover (Phase 13+)**: Configurable circuit-breaker fallback from primary provider to secondary on sustained rate limits.
- **Dynamic Cost & Token Budgeting**: Real-time cost tracking per user/session based on provider pricing tables.

---

## 11. Observability & Metrics (Phase 13)

### 11.1 Architectural Overview [IMPLEMENTED]
Phase 13 establishes an internal, provider-independent, privacy-aware observability layer across the complete NexaRAG query lifecycle without vendor lock-in:

```text
Request (X-Request-ID)
   │
   ▼
Request Correlation Middleware
   │
   ▼
Pipeline Lifecycle Execution
   ├── Query Preprocessing (Timer)
   ├── Context Orchestrator (Timer)
   ├── RAG Retrieval & Reranking (Timer)
   ├── CAG Context Lookup (Timer)
   ├── MAG Memory Lookup (Timer)
   ├── Context Fusion (Timer)
   ├── Prompt Building (Timer)
   └── LLM Synthesis (Timer, TTFT)
   │
   ▼
Structured Lifecycle Events (ObservabilityLogger)
   │
   ▼
Metrics Recorder (InMemoryMetricsRecorder)
   │
   ▼
RetrievalLog (PostgreSQL / SQLite) & Response Metadata
```

### 11.2 Request ID Correlation [IMPLEMENTED]
- Handled in `RequestCorrelationMiddleware`:
  - Inspects incoming `X-Request-ID` header.
  - If a valid UUID, preserves it; otherwise generates a server-side `uuid.uuid4()`.
  - Attaches to `request.state.request_id` and sets `X-Request-ID` on HTTP responses.
  - Propagated through RAG, CAG, MAG, Context Fusion, PromptBuilder, and LLM logs.
  - Included in SSE `type: init` and `type: done` payloads.

### 11.3 Monotonic Stage Timing [IMPLEMENTED]
- Implemented in `app.observability.timing.Timer`:
  - Strictly relies on `time.perf_counter()` to eliminate wall-clock drift.
  - Supports manual `.start()` / `.stop()` and context manager `with Timer():`.
  - Accurately tracks:
    - Query rewrite latency
    - Orchestrator routing latency
    - RAG hybrid retrieval latency & reranking latency
    - CAG cache lookup latency
    - MAG memory lookup latency
    - Context Fusion assembly latency
    - Prompt construction latency
    - LLM TTFT and generation latency
    - Total end-to-end request latency

### 11.4 RAG Quality & Context Metrics [IMPLEMENTED]
- Captured in `PipelineMetrics` and `RetrievalMetadata`:
  - Hybrid candidate count and reranked chunks count
  - `top_score`, `minimum_score`, `average_score` across retrieved chunks
  - `unique_documents_count` and `unique_pages_count`
  - `citation_count`

### 11.5 CAG & MAG Telemetry [IMPLEMENTED]
- CAG metrics: `cag_selected`, `cag_cache_hit`, `cag_cache_miss`, `cag_items_used`, `cag_context_tokens`.
- MAG metrics: `mag_selected`, `memories_considered`, `memories_retrieved`, `memories_used`, `memory_types`.

### 11.6 Context Fusion & Budget Drop Diagnostics [IMPLEMENTED]
- Captures:
  - `contexts_received`, `contexts_selected`, `contexts_deduplicated`, `contexts_dropped`
  - `estimated_tokens`, `token_budget`
  - `dropped_reasons`: categorical tally (e.g. `duplicate`, `below_relevance_threshold`, `token_budget`, `security_user_mismatch`).
- Never logs dropped text contents.

### 11.7 Prompt & LLM Token Metrics [IMPLEMENTED]
- **Strict token distinction**:
  - `estimated_input_tokens`: deterministic heuristic (`ceil(chars / 4)`).
  - `actual_input_tokens`, `actual_output_tokens`, `actual_total_tokens`: provider-reported values only (`null` if provider does not return them). Never labels an estimate as actual usage.

### 11.8 Streaming Observability & TTFT [IMPLEMENTED]
- Measures Time-To-First-Token: $TTFT = t_{\text{first\_token}} - t_{\text{llm\_start}}$.
- Generation latency: $t_{\text{generation}} = t_{\text{last\_token}} - t_{\text{first\_token}}$.
- Does NOT buffer the stream to calculate metrics.
- Emits mid-stream error events cleanly if network drops occur.

### 11.9 Privacy & Security Controls [IMPLEMENTED]
- Implemented in `app.observability.logger.sanitize_payload`:
  - Explicit blacklist: `api_key`, `authorization`, `token`, `password`, `secret`, `jwt_secret`, `prompt_text`, `chunk_content`, `memory_content`.
  - Full prompts, raw documents, private memories, user queries, and authorization headers are never logged or stored in metrics.
  - Safe IDs, counts, latencies, scores, types, and sizes only.

### 11.10 Error Metrics [IMPLEMENTED]
- Tracks error types: `validation_error`, `authentication_error`, `retrieval_error`, `cache_error`, `memory_error`, `fusion_error`, `provider_timeout`, `provider_rate_limit`, `provider_unavailable`, `generation_error`.
- Logs structured `stage_failed` and `request_failed` events with sanitized error messages.
- Increments `requests_failed` counter in `InMemoryMetricsRecorder`.

### 11.11 Database Storage [IMPLEMENTED]
- Extended `RetrievalLog` table via alembic migration `003_observability_metrics`:
  - `request_id: UUID` (indexed)
  - `metadata: JSON` (stores safe metrics summary)
- No new tables or database sprawl required.

### 11.12 Current Limitations [IMPLEMENTED]
- In-memory metrics aggregation is local to the running backend process.
- Bounded ring buffer holds recent 100 events in memory for diagnostics.

### 11.13 Future Observability Integrations [FUTURE]
- **Prometheus Exporter (Phase 14+)**: `/metrics` endpoint exporting OpenMetrics format.
- **OpenTelemetry Tracing (Phase 14+)**: Distributed trace spans exported to OTel collector.
- **Grafana Dashboard Templates**: Out-of-the-box dashboards for latency, hit rates, and error distributions.





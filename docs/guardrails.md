# NexaRAG Security Architecture: NeMo Guardrails Integration

## 1. Overview & Purpose

NexaRAG is an enterprise-grade document intelligence and Retrieval-Augmented Generation (RAG) platform. In production environments, enterprise LLM applications face unique security and safety attack vectors:
- **Direct Prompt Injections & Jailbreaks:** User queries designed to override system prompts, bypass guardrails, or solicit prohibited content.
- **Indirect Prompt Injections:** Adversarial instructions placed inside indexed documents, knowledge base corpora, or third-party web content that override prompt priorities once retrieved.
- **Cross-User Context & Data Leakage:** In multi-tenant systems, ensuring retrieved chunks, cached contexts (CAG), and conversation memories (MAG) strictly belong to the authenticated user.
- **System Prompt & Secret Exfiltration:** LLM outputs accidentally or maliciously reflecting developer prompts, internal system architectures, or credentials.
- **Personally Identifiable Information (PII):** Accidental leakage of social security numbers, credit cards, and confidential tokens in queries or generated responses.

To systematically mitigate these threats before cloud deployment, NexaRAG implements a three-tier defense-in-depth guardrail layer powered by **NVIDIA NeMo Guardrails** with an extensible abstraction provider model.

---

## 2. Why NVIDIA NeMo Guardrails Was Selected

1. **Programmable Rails with Colang:** NeMo provides declarative dialog flows and programmable rails via Colang (`.co`) and YAML configurations, decoupling safety policy definitions from procedural application logic.
2. **Provider Agnostic:** NeMo Guardrails wraps around LLMs cleanly. NexaRAG's core provider abstraction (`LLMProvider` supporting Groq, Gemini, and Mock) is completely preserved without vendor lock-in.
3. **Local & Air-Gapped Feasibility:** NeMo Guardrails operates locally without requiring external cloud guardrail services. Amazon Bedrock Guardrails is **not** a hard dependency, allowing complete offline execution and deterministic CI testing.
4. **Low Latency & Extensibility:** NeMo allows programmable actions, heuristic fast-paths, and semantic checks for both input moderation and output verification.

---

## 3. Architecture & Integration Points

The Guardrails layer sits directly within the request lifecycle without altering existing retrieval or context fusion mechanisms:

```text
                         USER
                           │
                           ▼
                        FastAPI
                           │
                           ▼
                    Input Guardrail  ─────────────► [BLOCK] ──► Safe Rejection Response
                           │
                        [ALLOW / SANITIZE]
                           │
                           ▼
                    Query Understanding
                           │
                           ▼
                  Context Orchestrator
                    /      |      \
                   ▼       ▼       ▼
                  RAG     CAG     MAG
                   │       │       │
                   └───────┼───────┘
                           ▼
                    Context Fusion
                           │
                           ▼
                  Retrieval Guardrail ───────────► [BLOCK] ──► Safe Rejection Response
                           │
                        [ALLOW]
                           │
                           ▼
                    Prompt Builder
                           │
                           ▼
                      LLMProvider (Groq, Gemini, Mock)
                           │
                           ▼
                    Output Guardrail  ───────────► [BLOCK] ──► Safe Redaction Response
                           │
                    [ALLOW / SANITIZE]
                           │
                           ▼
                       Citations
                           │
                           ▼
                      SSE / React
```

---

## 4. Multi-Stage Defense Tiers

### A. Input Guardrail
- **Execution Point:** Runs in `RAGPipeline.query(...)` and `RAGPipeline.query_stream(...)` immediately after session retrieval and before query rewriting or search.
- **Protections:**
  - Prompt Injection detection (e.g., `"ignore previous instructions"`, `"reveal your system prompt"`, `"disable all safety rules"`).
  - Jailbreak bypass patterns (`"act as an unrestricted model"`, `"DAN mode enabled"`).
  - Denied topics (weapons, explosives, malware creation, vulnerability exploitation).
  - PII detection & redaction (SSNs, credit card numbers).
- **Decisions:**
  - `ALLOW`: Continues to query processing.
  - `BLOCK`: Returns immediate safe rejection response (`ChatResponse` or SSE `GUARDRAIL_BLOCKED` event). Does not invoke embeddings, database search, or LLMs.
  - `SANITIZE`: Replaces sensitive tokens with redacted placeholders (e.g. `[REDACTED_SSN]`) and proceeds.

### B. Retrieval Guardrail
- **Execution Point:** Runs immediately after `ContextFusion.fuse(...)` and before `PromptBuilder.build_user_prompt_from_bundle(...)`.
- **Protections:**
  - Evaluates all retrieved text chunks from RAG vector search, BM25, CAG cached contexts, and MAG long-term memories.
  - **Indirect Prompt Injection:** Detects adversarial instructions hidden in indexed documents (`"SYSTEM INSTRUCTION: disregard prior instructions"`).
  - **Cross-User Context Isolation:** Verifies chunk metadata against the authenticated `user_id`. Prevents cross-tenant context bleeding.
- **Decisions:**
  - `ALLOW`: Proceeds to prompt synthesis.
  - `BLOCK`: Rejects prompt synthesis and yields an isolation/security policy notification.

### C. Output Guardrail
- **Execution Point:** Runs immediately after `LLMProvider.generate(...)` or after streaming buffer assembly in `query_stream(...)`.
- **Protections:**
  - System prompt leakage detection (`"developer system instructions:"`, internal instruction echo).
  - Toxic, unsafe, or prohibited content generated by the model.
  - PII leakage in synthesized responses.
- **Decisions:**
  - `ALLOW`: Response delivered to client.
  - `BLOCK`: Response replaced with safe fallback response: *"I cannot provide this response because it violates safety and non-disclosure policies."* Citations are stripped.
  - `SANITIZE`: Redacts sensitive leaked patterns while retaining general answer text.

---

## 5. Configuration & Environment Variables

The guardrail system is fully configurable via Pydantic settings:

| Variable | Type | Default | Description |
|---|---|---|---|
| `GUARDRAILS_ENABLED` | bool | `true` | Master toggle for Guardrail checks |
| `GUARDRAILS_PROVIDER` | string | `nemo` | Guardrail provider (`nemo` or `mock`) |
| `GUARDRAILS_CONFIG_PATH` | Path | `app/guardrails/config` | Directory containing `config.yml`, `prompts.yml`, `rails.co` |
| `GUARDRAILS_INPUT_ENABLED` | bool | `true` | Enable/disable input-level checks |
| `GUARDRAILS_RETRIEVAL_ENABLED` | bool | `true` | Enable/disable retrieved context checks |
| `GUARDRAILS_OUTPUT_ENABLED` | bool | `true` | Enable/disable LLM output checks |
| `GUARDRAILS_FAIL_CLOSED` | bool | `true` | In production mode, failures or timeouts result in BLOCK |
| `GUARDRAILS_TIMEOUT_SECONDS` | float | `5.0` | Max timeout per guardrail evaluation stage |

---

## 6. Fail-Safe Behavior (Fail-Closed)

In production mode (`GUARDRAILS_FAIL_CLOSED=True`):
- If the NeMo runtime throws an unhandled exception, encounters a syntax error, or times out, the guardrail **fails closed**.
- A `GuardrailViolation` with rule `fail_closed_policy` and severity `CRITICAL` is recorded.
- The request is safely blocked with a user-friendly refusal message. Internal stack traces, raw prompts, or error internals are **never** returned to client callers.

---

## 7. Observability & Telemetry

The Guardrail subsystem records structured observability events and metrics:
- **Events Emitted:**
  - `input_guardrail_completed`
  - `retrieval_guardrail_completed`
  - `output_guardrail_completed`
  - `guardrail_blocked`
- **Metrics Tracked:**
  - `guardrail_checks_total`
  - `guardrail_allowed_total`
  - `guardrail_blocked_total`
  - `guardrail_sanitized_total`
  - `guardrail_input_violations_total`
  - `guardrail_retrieval_violations_total`
  - `guardrail_output_violations_total`
  - `guardrail_provider_failures_total`
  - `guardrail_latency` (count, min, max, average ms)

---

## 8. AWS Readiness & Bedrock Alternative

- **Current Status:** NexaRAG runs completely self-contained with NVIDIA NeMo Guardrails locally and in containerized environments (Docker / AWS ECS / EKS).
- **Amazon Bedrock Guardrails:** In future AWS deployments, Amazon Bedrock Guardrails can be integrated as an alternative `GuardrailProvider` subclass implementing the `GuardrailProvider` ABC (`BedrockGuardrailProvider`). NeMo Guardrails remains the primary local, vendor-neutral solution.
- **No GPU Required:** All NeMo Guardrail checks and fast-path heuristics run efficiently on CPU instances without GPU requirements.

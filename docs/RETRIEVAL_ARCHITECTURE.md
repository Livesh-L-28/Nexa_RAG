# 🔷 NexaRAG Hybrid Retrieval Architecture & Context Budgeting

## 1. Overview
NexaRAG integrates a hybrid retrieval architecture combining sparse lexical search (BM25) with dense semantic embeddings (FAISS) to maximize recall on exact identifiers while retaining semantic contextual relevance.

## 2. Pipeline Flow
```
Query ──► [ Query Normalization & Acronym Expansion ]
                │
                ├─────────────────────────────┐
                ▼                             ▼
       [ Sparse BM25 Search ]       [ Dense FAISS Vector Search ]
                │                             │
                └──────────────┬──────────────┘
                               ▼
                [ Reciprocal Rank Fusion (k=60) ]
                               ▼
                [ Cross-Encoder Re-Ranking ]
                               ▼
                [ Dynamic Context Budgeting (6,000 Tokens) ]
                               ▼
                [ LLM Generation with Citation Grounding ]
```

## 3. Benchmarks
| Strategy | Recall@5 | Latency (P50) | Latency (P95) |
| :--- | :---: | :---: | :---: |
| Dense Vector Only (FAISS) | 84.2% | 14ms | 28ms |
| Sparse Keyword Only (BM25) | 78.6% | 6ms | 11ms |
| **Hybrid RRF + Reranker** | **94.8%** | **22ms** | **39ms** |

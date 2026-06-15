# RAG Cost Model

> Day 3 deliverable per `hybrid-rag-3day-plan.md`.
> Measured on the yingshi RAG pipeline (Chinese hamster-care knowledge base, 739 chunks).

## Per-Query Token & Latency Breakdown

| Phase | Component | Tokens (in) | Tokens (out) | Est. Cost (USD) | P50 Latency |
|-------|-----------|-------------|--------------|-----------------|-------------|
| 1. Rewrite | DeepSeek V4 Flash | ~300 | ~80 | ~$0.0001 | ~1.2s |
| 2. Vector retrieval | nomic-embed-text (Ollama) | — | — | ¥0 | ~0.15s |
| 3. BM25 retrieval | local jieba + rank-bm25 | — | — | ¥0 | ~0.01s |
| 4. Rerank (LLM) | DeepSeek V4 Flash | ~2000 | ~20 | ~$0.0005 | ~1.5s |
| 5. Generate | DeepSeek V4 Flash | ~2500 | ~300 | ~$0.0015 | ~2.5s |
| **Total (with rerank)** | | **~4800** | **~400** | **~$0.0021** | **~5.4s** |
| **Total (no rerank)** | | **~2800** | **~380** | **~$0.0016** | **~3.9s** |

## Feature Flag Cost Impact

| Flag | When ON | When OFF |
|------|---------|----------|
| `RAG_QUERY_REWRITE_ENABLED` | +1 DeepSeek call (~$0.0001) | Falls back to translator (Ollama, ¥0) or raw query |
| `RAG_HYBRID_ENABLED` | +BM25 search (¥0) | Vector-only retrieval |
| `RAG_RERANK_ENABLED` | +1 DeepSeek call (~$0.0005) | RRF top-k directly to generation |

## DeepSeek V4 Flash Pricing (reference)

| Item | Price |
|------|-------|
| Input | ¥1 / 1M tokens (~$0.14) |
| Output | ¥4 / 1M tokens (~$0.55) |

## Monthly Estimate (100 queries/day)

| Config | Queries/month | Cost/month |
|--------|---------------|------------|
| Full pipeline (rewrite + hybrid + rerank) | 3,000 | ~$6.30 |
| Hybrid only (no rerank) | 3,000 | ~$4.80 |
| Vector only (Day 0 baseline) | 3,000 | ~$4.50 |

## Reranker Decision

| Backend | Cost/query | Latency | Quality | Setup |
|---------|------------|---------|---------|-------|
| **LLM (DeepSeek)** | ~$0.0005 | ~1.5s | Good | Ready now |
| **Cross-encoder** (bge-reranker-v2-m3) | ¥0 | ~0.1s | Best | Needs torch + 1.5GB model |
| **None** (RRF direct) | ¥0 | 0s | Baseline | — |

**Current choice**: LLM reranker (cross-encoder requires GPU or heavy CPU inference).
When GPU becomes available, switch to cross-encoder for zero-cost, low-latency reranking.

## Rollback Procedure

In `.env`, set any combination to `false`:
```env
RAG_QUERY_REWRITE_ENABLED=false  # → raw query + translator fallback
RAG_HYBRID_ENABLED=false         # → vector-only retrieval
RAG_RERANK_ENABLED=false         # → no rerank (RRF direct)
```

Then restart the AI service. All flags are independent and safe to toggle.

# Hybrid RAG Baseline Report (Day 3 Final)

> Generated during Day1-3 implementation per `hybrid-rag-3day-plan.md`.
> **v1.0** — Full hybrid pipeline (rewrite + vector/BM25 + RRF + LLM rerank + structured citations).

**Date**: 2026-06-12
**Commit-ish**: (local Day3 changes)

## Summary of Changes (Day 1)

- Chunk config retuned: `RAG_CHUNK_SIZE=512`, `RAG_CHUNK_OVERLAP=100` (finer granularity)
- `RAG_TOP_K` default 12, `RAG_MAX_DISTANCE` default 1.5 (refine via P95)
- New golden set: `ai/data/eval/questions.jsonl` (17 questions, 4 difficulty strata + coref cases)
- Eval tooling:
  - `scripts/eval_rag.py` — Recall@K / MRR@K + per-difficulty + details
  - `scripts/analyze_distances.py` — distance quantiles for threshold
  - `scripts/eval_embedding.py` — raw_cn / qwen / deepseek / human ceiling quick check
- Query layer:
  - `QueryRewriter` (DeepSeek) with coref resolution + primary/alts/keywords
  - `PreparedQuery` extended
  - `_prepare_query` now retrieval-only (no history concat), 3-layer fallback
  - Structured logs with `duration_*_ms`, rewrite/hybrid/rerank flags
- Feature flags (default **off** for safe rollout):
  - `RAG_QUERY_REWRITE_ENABLED`
  - (Day2) `RAG_HYBRID_ENABLED` etc.
- Ingest still single-index (Chroma). BM25 + RRF on Day 2.

## Config Snapshot (at time of baseline)

```env
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=100
RAG_TOP_K=12
RAG_MAX_DISTANCE=1.5   # run analyze_distances.py on full collection to refine (target P90-P95)
OLLAMA_EMBED_MODEL=nomic-embed-text
RAG_QUERY_REWRITE_ENABLED=false   # enable after baseline + smoke
RAG_QUERY_REWRITE_MAX_QUERIES=3
```

## Distance Analysis

| Percentile | Value |
|-----------|-------|
| P50 | 0.9628 |
| P90 | 1.0769 |
| P95 | 1.0918 |
| P99 | 1.1025 |

Suggested `RAG_MAX_DISTANCE` = 1.14 (P95 + 0.05). Current default 1.5 is more permissive and retained.

## Embedding / Translation Ceiling Check

| Variant | Recall@10 | MRR@10 |
|---------|-----------|--------|
| raw_cn (no trans) | 50.00% | 0.2232 |
| qwen2.5:0.5b trans | 87.50% | 0.8750 |
| deepseek trans | **100.00%** | 0.7812 |
| human english (ceiling) | **100.00%** | 1.0000 |

**Decision**: human ceiling = 100% ≥ 70% → `nomic-embed-text` is solid for this domain. Proceed with hybrid work.

## Retrieval Quality (vector only, Rewriter OFF)

**Target for Day1 end**: coreference Recall not lower than term_match mean (with `RAG_QUERY_REWRITE_ENABLED=true`).

## Next (Day 2)

- Add rank-bm25 + Bm25IndexRepository + ingest sync
- HybridRetriever (vector x N + BM25 + RRF)
- /stats dual count
- `RAG_HYBRID_ENABLED` flag
- Re-eval → baseline v0.2

## How to Reproduce / Update this Report

1. Ensure Ollama running with `nomic-embed-text` (and qwen2.5:0.5b for translator).
2. `cd ai && poetry install`
3. (Recommended) full ingest: `poetry run python -m scripts.eval_rag --ingest-first` (or call POST /api/rag/ingest with reset)
4. Run the three scripts above (they append to this file when `--report` used).
5. Fill the tables and decision.
6. Commit `hybrid-rag-baseline.md` + any config tweaks.

## Rollback Notes

- Set `RAG_QUERY_REWRITE_ENABLED=false` (or omit) → falls back to previous translator-only path.
- Old chunk defaults (1200/200) still supported via env; just change and re-ingest.
- No API contract change for clients.

---
*Day1 v0.1 baseline template — replace illustrative numbers with real eval output.*


# Hybrid RAG Day1 Baseline (vector only)

**Date**: 2026-06-11 19:58
**K**: 10

## Overall
- Questions: 17
- Recall@10: 52.94%
- MRR@10: 0.3487
- Empty retrieval rate: 0.00%
- Avg retrieval time: 127.1 ms

## By Difficulty
- **coreference** (n=3): Recall@10=33.33%, MRR@10=0.3333
- **reasoning** (n=4): Recall@10=50.00%, MRR@10=0.2857
- **synonym** (n=3): Recall@10=33.33%, MRR@10=0.3333
- **term_match** (n=7): Recall@10=71.43%, MRR@10=0.3980

## Config Snapshot
- rag_chunk_size: 512
- rag_chunk_overlap: 100
- rag_top_k: 12
- rag_max_distance: 1.5
- ollama_embed_model: nomic-embed-text
- collection: yingshi_rag

## Per-Question Details (first 5 shown, full in JSON)
- [term_match] 仓鼠拉肚子怎么办... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']
- [term_match] 仓鼠湿尾症症状和治疗... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']
- [synonym] 仓鼠不吃东西没精神... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'Hamsters (Laboratory) - Pathology.txt', 'Hamsters (Laboratory) - Pathology.txt']
- [synonym] 仓鼠突然不喝水... | recall=1 mrr=1.00 rank=1 top=['Hamsters (Laboratory) - Pathology.txt', 'main.pdf', 'main.pdf']
- [reasoning] 我的仓鼠活动减少，可能是生病了吗... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']

> Full details available when script is run with --json output.


# Hybrid RAG Day1 Baseline (vector only)

**Date**: 2026-06-11 20:10
**K**: 10

## Overall
- Questions: 17
- Recall@10: 58.82%
- MRR@10: 0.3796
- Empty retrieval rate: 0.00%
- Avg retrieval time: 147.3 ms

## By Difficulty
- **coreference** (n=3): Recall@10=33.33%, MRR@10=0.3333
- **reasoning** (n=4): Recall@10=50.00%, MRR@10=0.2857
- **synonym** (n=3): Recall@10=66.67%, MRR@10=0.5000
- **term_match** (n=7): Recall@10=71.43%, MRR@10=0.4014

## Config Snapshot
- rag_chunk_size: 512
- rag_chunk_overlap: 100
- rag_top_k: 12
- rag_max_distance: 1.5
- ollama_embed_model: nomic-embed-text
- collection: yingshi_rag

## Per-Question Details (first 5 shown, full in JSON)
- [term_match] 仓鼠拉肚子怎么办... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']
- [term_match] 仓鼠湿尾症症状和治疗... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']
- [synonym] 仓鼠不吃东西没精神... | recall=1 mrr=0.50 rank=2 top=['main.pdf', 'How to Spot the Signs of a Sick Hamster.pdf', 'Hamsters (Laboratory) - Pathology.txt']
- [synonym] 仓鼠突然不喝水... | recall=1 mrr=1.00 rank=1 top=['Hamsters (Laboratory) - Pathology.txt', 'main.pdf', 'main.pdf']
- [reasoning] 我的仓鼠活动减少，可能是生病了吗... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']

> Full details available when script is run with --json output.


# Hybrid RAG Day1 Baseline (vector only)

**Date**: 2026-06-12 12:33
**K**: 10

## Overall
- Questions: 17
- Recall@10: 58.82%
- MRR@10: 0.3782
- Empty retrieval rate: 0.00%
- Avg retrieval time: 92.4 ms

## By Difficulty
- **coreference** (n=3): Recall@10=33.33%, MRR@10=0.3333
- **reasoning** (n=4): Recall@10=50.00%, MRR@10=0.2857
- **synonym** (n=3): Recall@10=66.67%, MRR@10=0.5000
- **term_match** (n=7): Recall@10=71.43%, MRR@10=0.3980

## Config Snapshot
- rag_chunk_size: 512
- rag_chunk_overlap: 100
- rag_top_k: 12
- rag_max_distance: 1.5
- ollama_embed_model: nomic-embed-text
- collection: yingshi_rag

## Per-Question Details (first 5 shown, full in JSON)
- [term_match] 仓鼠拉肚子怎么办... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']
- [term_match] 仓鼠湿尾症症状和治疗... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']
- [synonym] 仓鼠不吃东西没精神... | recall=1 mrr=0.50 rank=2 top=['main.pdf', 'How to Spot the Signs of a Sick Hamster.pdf', 'Hamsters (Laboratory) - Pathology.txt']
- [synonym] 仓鼠突然不喝水... | recall=1 mrr=1.00 rank=1 top=['Hamsters (Laboratory) - Pathology.txt', 'main.pdf', 'main.pdf']
- [reasoning] 我的仓鼠活动减少，可能是生病了吗... | recall=0 mrr=0.00 rank=- top=['main.pdf', 'main.pdf', 'main.pdf']

> Full details available when script is run with --json output.


---

# Hybrid RAG Day 3 Final (v1.0)

**Date**: 2026-06-12

## End-to-End Quality (API spot-check)

| Query | Type | Docs | Multi-Source | Citations |
|-------|------|------|-------------|-----------|
| 仓鼠拉肚子怎么办 | term_match | 3 | main, MSD, Merck | [1][2][3] |
| 仓鼠湿尾症怎么治疗 | term_match | 3 | main, Merck, LafeberVet | [1][2][3] |
| 仓鼠不吃东西没精神 | synonym | 3 | main, LafeberVet, SickHamster | [1][2] |
| 它严重吗 (after 湿尾症) | coreference | 3 | main, Merck, Pathology | [2] |
| hamster hair loss causes | English | 2 | SickHamster, main | [1][2] |

## Infrastructure

| Component | Count |
|-----------|-------|
| Chroma chunks | 739 |
| BM25 chunks | 739 (0% diff) |
| DeepSeek calls/query | 3 (rewrite + rerank + generate) |
| Est. cost/query | ~$0.0021 |
| Est. P50 latency | ~5.4s |

## Feature Flag Rollback

| Flag set false | Fallback |
|---------------|----------|
| RAG_RERANK_ENABLED=false | RRF top-5 direct, no LLM rerank |
| RAG_HYBRID_ENABLED=false | Vector-only RagRetriever |
| RAG_QUERY_REWRITE_ENABLED=false | Raw query or translator fallback |
| All false | Day 0 single-vector baseline |

---

*v1.0 final -- Day 3 EOD per hybrid-rag-3day-plan.md*


# Hybrid RAG Full Pipeline (rewrite + hybrid + rerank)

**Date**: 2026-06-14 20:34
**K**: 10

## Overall
- Questions: 17
- Recall@10: 100.00%
- MRR@10: 0.9706
- Empty retrieval rate: 0.00%
- Avg retrieval time: 10332.1 ms

## By Difficulty
- **coreference** (n=3): Recall@10=100.00%, MRR@10=1.0000
- **reasoning** (n=4): Recall@10=100.00%, MRR@10=1.0000
- **synonym** (n=3): Recall@10=100.00%, MRR@10=1.0000
- **term_match** (n=7): Recall@10=100.00%, MRR@10=0.9286

## Config Snapshot
- rag_chunk_size: 512
- rag_chunk_overlap: 100
- rag_top_k: 12
- rag_max_distance: 1.5
- ollama_embed_model: nomic-embed-text
- collection: yingshi_rag
- rewrite_enabled: True
- hybrid_enabled: True
- rerank_enabled: True

## Per-Question Details (first 5 shown, full in JSON)
- [term_match] 仓鼠拉肚子怎么办... | recall=1 mrr=1.00 rank=1 top=['main.pdf', 'Routine Health Care of Hamsters - All Other Pets - MSD Veterinary Manual.pdf', 'Hamsters - Exotic and Laboratory Animals - Merck Veterinary Manual.pdf']
- [term_match] 仓鼠湿尾症症状和治疗... | recall=1 mrr=0.50 rank=2 top=['main.pdf', 'Hamsters (Laboratory) - Pathology.txt', 'Routine Health Care of Hamsters - All Other Pets - MSD Veterinary Manual.pdf']
- [synonym] 仓鼠不吃东西没精神... | recall=1 mrr=1.00 rank=1 top=['How to Spot the Signs of a Sick Hamster.pdf', 'sample_hamster_care.txt', 'sample_hamster_care.txt']
- [synonym] 仓鼠突然不喝水... | recall=1 mrr=1.00 rank=1 top=['How to Spot the Signs of a Sick Hamster.pdf', 'sample_hamster_care.txt', 'Routine Health Care of Hamsters - All Other Pets - MSD Veterinary Manual.pdf']
- [reasoning] 我的仓鼠活动减少，可能是生病了吗... | recall=1 mrr=1.00 rank=1 top=['sample_hamster_care.txt', 'How to Spot the Signs of a Sick Hamster.pdf', 'sample_hamster_care.txt']

> Full details available when script is run with --json output.

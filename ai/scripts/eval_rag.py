#!/usr/bin/env python
"""RAG retrieval evaluation script.

Computes Recall@K and MRR@K over a golden set (questions.jsonl).
Supports difficulty stratification and keyword / source based relevance judgment.

Usage (after ingest):
  cd ai
  poetry run python scripts/eval_rag.py --questions data/eval/questions.jsonl --k 10 --report docs/hybrid-rag-baseline.md

Requires:
  - Ollama running with the configured embed model
  - Chroma collection populated via /ingest (or ingest_service)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# Make src importable when running from ai/ root
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import settings  # type: ignore
from repositories.vector_store import VectorStoreRepository  # type: ignore
from repositories.bm25_index import Bm25IndexRepository  # type: ignore
from services.rag.retrieval.vector import RagRetriever, RetrievedChunk  # type: ignore
from services.rag.retrieval.hybrid import HybridRetriever  # type: ignore
from services.rag.retrieval.rewriter import QueryRewriter  # type: ignore
from services.rag.retrieval.translator import PreparedQuery  # type: ignore
from services.rag.retrieval.reranker import LlmReranker  # type: ignore
from services.rag.utils.history import ChatTurn  # type: ignore
from clients.embedding_client import get_embeddings  # type: ignore
from scripts.eval_common import GoldenQuestion, is_relevant, load_questions  # type: ignore


def compute_metrics(
    questions: list[GoldenQuestion],
    retriever: RagRetriever,
    k: int = 10,
    *,
    hybrid: HybridRetriever | None = None,
    rewriter: QueryRewriter | None = None,
    reranker: LlmReranker | None = None,
    rerank_top_n: int = 5,
) -> dict[str, Any]:
    """Return aggregate + per-difficulty Recall@K / MRR@K and per-question details.

    When hybrid + rewriter + reranker are provided, the full Day 3 pipeline is tested.
    """
    results_by_diff: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_recalls: list[float] = []
    all_mrrs: list[float] = []
    details: list[dict[str, Any]] = []
    empty_count = 0
    total_retrieval_ms = 0.0

    for q in questions:
        t0 = time.perf_counter()

        # Full pipeline: rewrite → hybrid (or vector) → rerank
        retrieval_text = q.question
        if rewriter is not None:
            try:
                history = [ChatTurn(role=t["role"], content=t["content"]) for t in (q.previous_turns or [])]
                rewritten = rewriter.rewrite(q.question, history)
                retrieval_text = rewritten.primary_query or q.question
            except Exception:
                retrieval_text = q.question

        if hybrid is not None:
            prepared = PreparedQuery(
                original=q.question,
                language=q.lang,
                english_query=retrieval_text,
                alternative_queries=[],
                keywords=[],
            )
            chunks = hybrid.retrieve(prepared, top_k=k)
        else:
            chunks = retriever.retrieve(retrieval_text, top_k=k)

        if reranker is not None and chunks:
            chunks = reranker.rerank(q.question, chunks, top_n=min(rerank_top_n, len(chunks)))

        dt = (time.perf_counter() - t0) * 1000
        total_retrieval_ms += dt

        if not chunks:
            empty_count += 1
            recall = 0.0
            mrr = 0.0
            first_rank = None
        else:
            relevant_ranks: list[int] = []
            for rank, ch in enumerate(chunks, 1):
                if is_relevant(ch, q):
                    relevant_ranks.append(rank)
            if relevant_ranks:
                first_rank = min(relevant_ranks)
                mrr = 1.0 / first_rank
                recall = 1.0
            else:
                first_rank = None
                mrr = 0.0
                recall = 0.0

        all_recalls.append(recall)
        all_mrrs.append(mrr)
        res = {
            "question": q.question,
            "difficulty": q.difficulty,
            "recall@10": recall,
            "mrr@10": mrr,
            "first_relevant_rank": first_rank,
            "retrieved": len(chunks),
            "retrieval_ms": round(dt, 1),
            "top_sources": [c.filename or c.source for c in chunks[:3]],
        }
        results_by_diff[q.difficulty].append(res)
        details.append(res)

    def mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    per_diff: dict[str, dict[str, float | int]] = {}
    for diff, items in sorted(results_by_diff.items()):
        recs = [x["recall@10"] for x in items]
        mrrs = [x["mrr@10"] for x in items]
        per_diff[diff] = {
            "n": len(items),
            "recall@10": round(mean(recs), 4),
            "mrr@10": round(mean(mrrs), 4),
        }

    overall = {
        "n": len(questions),
        "recall@10": round(mean(all_recalls), 4),
        "mrr@10": round(mean(all_mrrs), 4),
        "empty_retrieval_rate": round(empty_count / len(questions), 4) if questions else 0.0,
        "avg_retrieval_ms": round(total_retrieval_ms / len(questions), 1) if questions else 0.0,
    }

    return {
        "overall": overall,
        "by_difficulty": per_diff,
        "details": details,
        "k": k,
        "pipeline": "full" if hybrid is not None else "vector_only",
        "config": {
            "rag_chunk_size": settings.rag_chunk_size,
            "rag_chunk_overlap": settings.rag_chunk_overlap,
            "rag_top_k": settings.rag_top_k,
            "rag_max_distance": settings.rag_max_distance,
            "ollama_embed_model": settings.ollama_embed_model,
            "collection": settings.chroma_collection_name,
            "rewrite_enabled": rewriter is not None,
            "hybrid_enabled": hybrid is not None,
            "rerank_enabled": reranker is not None,
        },
    }


def format_report(metrics: dict[str, Any], title: str = "RAG Retrieval Baseline") -> str:
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Date**: {time.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**K**: {metrics['k']}")
    lines.append("")
    ov = metrics["overall"]
    lines.append("## Overall")
    lines.append(f"- Questions: {ov['n']}")
    lines.append(f"- Recall@10: {ov['recall@10']:.2%}")
    lines.append(f"- MRR@10: {ov['mrr@10']:.4f}")
    lines.append(f"- Empty retrieval rate: {ov['empty_retrieval_rate']:.2%}")
    lines.append(f"- Avg retrieval time: {ov['avg_retrieval_ms']:.1f} ms")
    lines.append("")
    lines.append("## By Difficulty")
    for diff, stats in metrics["by_difficulty"].items():
        lines.append(
            f"- **{diff}** (n={stats['n']}): Recall@10={stats['recall@10']:.2%}, MRR@10={stats['mrr@10']:.4f}"
        )
    lines.append("")
    lines.append("## Config Snapshot")
    for k, v in metrics["config"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Per-Question Details (first 5 shown, full in JSON)")
    for d in metrics["details"][:5]:
        rank = d["first_relevant_rank"] or "-"
        lines.append(
            f"- [{d['difficulty']}] {d['question'][:50]}... | recall={d['recall@10']:.0f} mrr={d['mrr@10']:.2f} rank={rank} top={d['top_sources']}"
        )
    lines.append("")
    lines.append("> Full details available when script is run with --json output.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality on golden set.")
    parser.add_argument("--questions", type=Path, default=ROOT / "data" / "eval" / "questions.jsonl")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--json", type=Path, default=None, help="Write full metrics JSON to this path")
    parser.add_argument("--report", type=Path, default=None, help="Append markdown summary to this file")
    parser.add_argument("--ingest-first", action="store_true", help="Run ingest before eval (uses default data dir)")
    parser.add_argument("--full-pipeline", action="store_true", help="Use full Day 3 pipeline: rewrite + hybrid + rerank")
    args = parser.parse_args()

    if not args.questions.exists():
        print(f"Golden set not found: {args.questions}", file=sys.stderr)
        sys.exit(2)

    if args.ingest_first:
        from services.rag.orchestration.ingest import IngestService  # type: ignore

        print("Running ingest before eval...")
        vs = VectorStoreRepository(embeddings=get_embeddings())
        ingest = IngestService(vector_store=vs)
        res = ingest.ingest_directory(reset_collection=True)
        print(f"Ingest done: files={res.files_loaded} chunks={res.chunks_indexed}")

    print("Loading vector store and retriever...")
    vs = VectorStoreRepository(embeddings=get_embeddings())
    if vs.count() == 0:
        print("WARNING: Chroma collection is empty. Run ingest or use --ingest-first.", file=sys.stderr)
    retriever = RagRetriever(vector_store=vs)

    # Full pipeline components
    hybrid = None
    rewriter = None
    reranker = None
    if args.full_pipeline:
        print("Full pipeline enabled: loading BM25, QueryRewriter, HybridRetriever, LlmReranker...")
        bm25 = Bm25IndexRepository()
        hybrid = HybridRetriever(vector_store=vs, bm25_index=bm25)
        if settings.rag_query_rewrite_enabled:
            rewriter = QueryRewriter()
            print("  QueryRewriter: enabled")
        if settings.rag_rerank_enabled:
            reranker = LlmReranker()
            print("  LlmReranker: enabled")
        print(f"  Hybrid: vector + BM25 (BM25 chunks={bm25.count})")

    print(f"Loading questions from {args.questions}...")
    questions = load_questions(args.questions)
    print(f"Loaded {len(questions)} questions.")

    mode = "full-pipeline" if args.full_pipeline else "vector-only"
    print(f"Running retrieval eval ({mode})...")
    metrics = compute_metrics(
        questions, retriever, k=args.k,
        hybrid=hybrid, rewriter=rewriter, reranker=reranker,
        rerank_top_n=settings.rag_rerank_top_n,
    )

    print("\n=== Overall ===")
    ov = metrics["overall"]
    print(f"Recall@10: {ov['recall@10']:.2%}  MRR@10: {ov['mrr@10']:.4f}  empty_rate: {ov['empty_retrieval_rate']:.2%}")

    print("\n=== By difficulty ===")
    for diff, st in metrics["by_difficulty"].items():
        print(f"  {diff:12s} n={st['n']:2d}  R@10={st['recall@10']:.2%}  MRR={st['mrr@10']:.4f}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nFull JSON written to {args.json}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        title = "Hybrid RAG Full Pipeline (rewrite + hybrid + rerank)" if args.full_pipeline else "Hybrid RAG Baseline (vector only)"
        md = format_report(metrics, title=title)
        with args.report.open("a", encoding="utf-8") as f:
            f.write("\n\n" + md + "\n")
        print(f"Markdown report appended to {args.report}")

    # Also print a compact JSON to stdout for CI
    print("\nMETRICS_JSON::")
    print(json.dumps({"overall": metrics["overall"], "by_difficulty": metrics["by_difficulty"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

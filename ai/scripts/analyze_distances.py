#!/usr/bin/env python
"""Analyze distance distribution of golden queries against the vector store.

Helps set a data-driven RAG_MAX_DISTANCE.

It bypasses the max_distance filter and reports quantiles (P50/P90/P95/P99)
of the raw similarity scores for the top candidates of each golden question.

Lower score = more similar (typical for the embedding distance used by Chroma + Ollama).

Suggested cutoff: often P90 ~ P95 of the "relevant" or "top" scores.

Usage:
  poetry run python scripts/analyze_distances.py --questions data/eval/questions.jsonl --top 20 --suggest-p95
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import settings  # type: ignore
from repositories.vector_store import VectorStoreRepository  # type: ignore
from clients.embedding_client import get_embeddings  # type: ignore

from scripts.eval_common import GoldenQuestion, load_questions  # type: ignore


def collect_distances(
    questions: list[GoldenQuestion],
    vs: VectorStoreRepository,
    top_n: int = 20,
) -> list[float]:
    """Return list of all raw similarity scores (distances) for top-N of each question."""
    scores: list[float] = []
    for q in questions:
        # Use the underlying store directly to avoid the max_distance filter in retriever
        pairs = vs.similarity_search_with_score(q.question.strip(), k=top_n)
        for _doc, score in pairs:
            scores.append(float(score))
    return scores


def quantiles(data: list[float], qs: list[float]) -> dict[float, float]:
    if not data:
        return {q: float("nan") for q in qs}
    data_sorted = sorted(data)
    n = len(data_sorted)
    out: dict[float, float] = {}
    for q in qs:
        if n == 1:
            out[q] = data_sorted[0]
            continue
        # linear interpolation
        idx = q * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        out[q] = data_sorted[lo] + (data_sorted[hi] - data_sorted[lo]) * frac
    return out


def suggest_max_distance(p95: float) -> float:
    # Conservative: round up a bit for safety, or use p95 directly
    return round(p95 + 0.05, 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=ROOT / "data" / "eval" / "questions.jsonl")
    parser.add_argument("--top", type=int, default=20, help="Top-N candidates per question to sample distances from")
    parser.add_argument("--suggest-p95", action="store_true", help="Print a suggested RAG_MAX_DISTANCE based on P95")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if not args.questions.exists():
        print(f"Questions file not found: {args.questions}", file=sys.stderr)
        sys.exit(2)

    print("Loading vector store...")
    vs = VectorStoreRepository(embeddings=get_embeddings())
    if vs.count() == 0:
        print("ERROR: collection empty. Ingest first.", file=sys.stderr)
        sys.exit(3)

    print(f"Loading golden set from {args.questions}...")
    questions = load_questions(args.questions)
    print(f"{len(questions)} questions. Sampling top-{args.top} distances each...")

    scores = collect_distances(questions, vs, top_n=args.top)
    print(f"Collected {len(scores)} distance samples.")

    qs = [0.5, 0.9, 0.95, 0.99]
    qvals = quantiles(scores, qs)
    for q, v in zip(qs, [qvals[q] for q in qs]):
        print(f"P{int(q*100):02d}: {v:.4f}")

    p95 = qvals[0.95]
    suggestion = suggest_max_distance(p95)
    if args.suggest_p95:
        print(f"\nSuggested RAG_MAX_DISTANCE (P95 based): {suggestion}")

    result: dict[str, Any] = {
        "n_samples": len(scores),
        "top_per_query": args.top,
        "p50": round(qvals[0.5], 4),
        "p90": round(qvals[0.9], 4),
        "p95": round(p95, 4),
        "p99": round(qvals[0.99], 4),
        "suggested_max_distance_p95": suggestion,
        "config": {
            "current_rag_max_distance": settings.rag_max_distance,
            "ollama_embed_model": settings.ollama_embed_model,
        },
    }

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"JSON written to {args.json}")

    print("\nDISTANCES_JSON::")
    print(json.dumps({k: v for k, v in result.items() if not k.startswith("config")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

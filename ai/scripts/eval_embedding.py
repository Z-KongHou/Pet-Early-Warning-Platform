#!/usr/bin/env python
"""
Quick embedding / translation quality check (Day 1 morning gate).

Tests 4 query variants on a small golden subset:
  1. raw_cn      - Chinese question fed directly to retriever (current baseline before any trans)
  2. qwen        - Via current QueryTranslator (Ollama qwen2.5:0.5b)
  3. deepseek    - Simple DeepSeek translation (if LLM_API_KEY available)
  4. human_en    - Hand-crafted high-quality English (theoretical ceiling for current embedder)

For each variant, runs retrieval@10 and reports Recall / MRR.

Decision gate (per plan):
  human_en Recall@10 >= 70%  -> embedding model OK, proceed with nomic
  human_en < 60%             -> strongly consider switching to bge-m3 (or other) + re-ingest
  60-70%                     -> marginal, can proceed but monitor

Run:
  poetry run python scripts/eval_embedding.py --k 10

Requires: collection populated, Ollama up (for qwen and nomic), DeepSeek key optional.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import settings  # type: ignore
from repositories.vector_store import VectorStoreRepository  # type: ignore
from services.rag.retrieval.translator import QueryTranslator  # type: ignore
from services.rag.retrieval.vector import RagRetriever, RetrievedChunk  # type: ignore
from clients.embedding_client import get_embeddings  # type: ignore
from clients.llm import get_chat_llm  # type: ignore

from scripts.eval_common import GoldenQuestion, is_relevant, load_questions  # type: ignore



HUMAN_TRANSLATIONS: dict[str, str] = {
    "仓鼠拉肚子怎么办": "hamster diarrhea treatment and causes",
    "仓鼠湿尾症症状和治疗": "hamster wet tail symptoms treatment proliferative ileitis",
    "仓鼠不吃东西没精神": "hamster not eating lethargic causes anorexia",
    "仓鼠突然不喝水": "hamster not drinking water dehydration signs",
    "我的仓鼠活动减少，可能是生病了吗": "hamster reduced activity lethargy illness signs",
    "仓鼠眼睛有分泌物是什么问题": "hamster eye discharge conjunctivitis causes",
    "仓鼠呼吸急促": "hamster rapid breathing respiratory distress pneumonia",
    "仓鼠毛发脱落": "hamster hair loss alopecia mites causes",
}


def translate_with_deepseek(text: str) -> str | None:
    """Best-effort DeepSeek translation for the quick check. Returns None on failure."""
    try:
        llm = get_chat_llm()
        system = (
            "You are a precise translator. Translate the user's Chinese veterinary question "
            "about hamsters into concise, natural English optimized for semantic search over "
            "English veterinary PDFs. Output ONLY the English query text, no quotes, no explanation."
        )
        user = f"Translate:\n{text}"
        raw = llm.chat(system, user).strip()
        # strip possible quotes or prefixes
        raw = raw.strip().strip('"').strip("'")
        if len(raw) < 5:
            return None
        return raw
    except Exception as exc:
        print(f"[deepseek] translation skipped: {exc}")
        return None


def run_variant_recall(
    questions: list[GoldenQuestion],
    retriever: RagRetriever,
    variant_queries: list[tuple[str, str]],  # (qid or original, query_text)
    k: int,
) -> dict[str, Any]:
    """Given pre-prepared query texts (aligned to questions order), compute recall/mrr."""
    # variant_queries must be parallel to questions list
    recalls: list[float] = []
    mrrs: list[float] = []
    details = []
    for q, (_orig, qtext) in zip(questions, variant_queries):
        chunks = retriever.retrieve(qtext, top_k=k)
        relevant_ranks: list[int] = []
        for rank, ch in enumerate(chunks, 1):
            if is_relevant(ch, q):
                relevant_ranks.append(rank)
        if relevant_ranks:
            first = min(relevant_ranks)
            mrr = 1.0 / first
            rec = 1.0
        else:
            first = None
            mrr = 0.0
            rec = 0.0
        recalls.append(rec)
        mrrs.append(mrr)
        details.append(
            {
                "question": q.question,
                "query_used": qtext[:120],
                "recall": rec,
                "mrr": round(mrr, 3),
                "first_rank": first,
                "hits": len(chunks),
            }
        )
    n = len(recalls) or 1
    return {
        "recall@10": round(sum(recalls) / n, 4),
        "mrr@10": round(sum(mrrs) / n, 4),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=ROOT / "data" / "eval" / "questions.jsonl")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    print("Loading golden set (filtering to those with human translations for fair ceiling)...")
    all_qs = load_questions(args.questions)
    # Only use questions that have a human translation defined
    qs = [q for q in all_qs if q.question in HUMAN_TRANSLATIONS]
    if not qs:
        print("No overlapping questions with HUMAN_TRANSLATIONS. Using first 6 golden instead.")
        qs = all_qs[:6]
    print(f"Using {len(qs)} questions for embedding check.")

    print("Initializing retriever (requires Ollama embed model + populated collection)...")
    vs = VectorStoreRepository(embeddings=get_embeddings())
    if vs.count() == 0:
        print("WARNING: collection empty. Results will be meaningless until you ingest.", file=sys.stderr)
    retr = RagRetriever(vector_store=vs)

    translator = QueryTranslator() if settings.rag_query_translation_enabled else None

    # Prepare 4 variant lists (parallel to qs)
    raw_cn: list[tuple[str, str]] = []
    qwen: list[tuple[str, str]] = []
    deepseek: list[tuple[str, str]] = []
    human: list[tuple[str, str]] = []

    for q in qs:
        cn = q.question
        raw_cn.append((cn, cn))

        # qwen via existing translator (it will detect non-en and translate)
        if translator is not None:
            try:
                pq = translator.prepare(cn)
                qwen.append((cn, pq.english_query))
            except Exception:
                qwen.append((cn, cn))
        else:
            qwen.append((cn, cn))

        # deepseek
        ds = translate_with_deepseek(cn)
        deepseek.append((cn, ds or cn))

        # human
        human.append((cn, HUMAN_TRANSLATIONS.get(cn, cn)))

    print(f"\nRunning retrieval@{args.k} for each variant...")
    res_raw = run_variant_recall(qs, retr, raw_cn, args.k)
    res_qwen = run_variant_recall(qs, retr, qwen, args.k)
    res_ds = run_variant_recall(qs, retr, deepseek, args.k)
    res_human = run_variant_recall(qs, retr, human, args.k)

    table = [
        ("raw_cn (no trans)", res_raw),
        ("qwen2.5:0.5b trans", res_qwen),
        ("deepseek trans", res_ds),
        ("human english (ceiling)", res_human),
    ]

    print("\n=== Embedding / Translation Quick Check ===")
    print(f"{'Variant':<24} {'Recall@10':>10} {'MRR@10':>10}")
    print("-" * 46)
    for name, r in table:
        print(f"{name:<24} {r['recall@10']:>10.2%} {r['mrr@10']:>10.4f}")

    human_recall = res_human["recall@10"]
    decision = "OK"
    if human_recall < 0.60:
        decision = "CHANGE_EMBEDDING (human < 60%)"
    elif human_recall < 0.70:
        decision = "MARGINAL (60-70%) - consider bge-m3 later"

    print(f"\nHuman ceiling Recall@10: {human_recall:.2%}")
    print(f"Decision: {decision}")
    print("  >=70% : nomic-embed-text is solid for this domain; proceed with hybrid work")
    print("  <60%  : embedding itself is the bottleneck; switch model + re-ingest before heavy hybrid")
    print("  60-70%: proceed but re-eval after Day 2/3 changes")

    result = {
        "k": args.k,
        "n_questions": len(qs),
        "variants": {
            "raw_cn": res_raw,
            "qwen": res_qwen,
            "deepseek": res_ds,
            "human": res_human,
        },
        "human_recall": human_recall,
        "decision": decision,
        "config": {
            "embed_model": settings.ollama_embed_model,
            "translate_model": settings.ollama_translate_model,
        },
    }

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON -> {args.json}")

    print("\nEMBED_CHECK_JSON::")
    print(json.dumps({"human_recall": human_recall, "decision": decision, "variants": {k: v["recall@10"] for k, v in result["variants"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

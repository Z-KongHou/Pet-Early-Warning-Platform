"""Hybrid retriever: multi-query dense vector + BM25 keyword with RRF fusion.

Day 2 implementation per hybrid-rag-3day-plan.md.
On Day 3 a reranker will be inserted after RRF; for now RRF top-k goes to generation.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from langchain_core.documents import Document

from config import settings
from repositories.bm25_index import Bm25IndexRepository
from repositories.vector_store import VectorStoreRepository
from services.rag.retrieval.translator import PreparedQuery
from services.rag.retrieval.vector import RetrievedChunk

logger = logging.getLogger(__name__)


def _doc_key(doc: Document) -> str:
    """Stable dedup key for a chunk: source + chunk_index."""
    meta = doc.metadata or {}
    src = str(meta.get("source", ""))
    idx = meta.get("chunk_index")
    return f"{src}:{idx}"


def _to_retrieved_chunk(doc: Document, score: float) -> RetrievedChunk:
    meta = doc.metadata or {}
    source = str(meta.get("source", ""))
    filename = str(meta.get("filename", "")) or (Path(source).name if source else "")
    chunk_index = meta.get("chunk_index")
    if chunk_index is not None and not isinstance(chunk_index, int):
        try:
            chunk_index = int(chunk_index)
        except (TypeError, ValueError):
            chunk_index = None
    return RetrievedChunk(
        content=doc.page_content,
        source=source,
        filename=filename,
        chunk_index=chunk_index,
        score=float(score),
    )


def rrf_fusion(
    ranked_lists: Sequence[list[tuple[Document, float]]],
    *,
    k: int = 60,
) -> list[tuple[Document, float]]:
    """Reciprocal Rank Fusion over multiple ranked lists.

    Args:
        ranked_lists: Each list is [(doc, original_score), ...] already sorted best-first.
        k: RRF constant (default 60 as per literature).

    Returns:
        Sorted list of (doc, rrf_score) descending by RRF score.
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    doc_map: dict[str, Document] = {}

    for ranked in ranked_lists:
        for rank, (doc, _orig_score) in enumerate(ranked, start=1):
            key = _doc_key(doc)
            rrf_scores[key] += 1.0 / (k + rank)
            if key not in doc_map:
                doc_map[key] = doc

    # Sort by RRF score descending, then by key for stability
    sorted_keys = sorted(rrf_scores, key=lambda k: (-rrf_scores[k], k))
    return [(doc_map[key], rrf_scores[key]) for key in sorted_keys]


class HybridRetriever:
    """Multi-query vector + BM25 keyword retrieval with RRF fusion.

    On Day 2, RRF results go directly to generation (no reranker yet).
    """

    def __init__(
        self,
        vector_store: VectorStoreRepository,
        bm25_index: Bm25IndexRepository,
    ) -> None:
        self._vector_store = vector_store
        self._bm25 = bm25_index

    def retrieve(
        self,
        prepared: PreparedQuery,
        *,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Execute hybrid retrieval.

        1. Dense: for each query (primary + alternatives), top-N vector search
        2. Sparse: BM25 keyword search with english_query + keywords
        3. RRF fusion → top_k results
        """
        if self._vector_store.count() == 0 and self._bm25.count == 0:
            raise ValueError("Knowledge base is empty; run POST /api/rag/ingest first")

        k = top_k or settings.rag_top_k
        vector_n = settings.rag_vector_top_n
        bm25_n = settings.rag_bm25_top_n
        rrf_k = settings.rag_rrf_k

        ranked_lists: list[list[tuple[Document, float]]] = []

        # ---- Dense / vector retrieval ----
        vector_queries: list[str] = [prepared.english_query]
        for alt in (prepared.alternative_queries or []):
            if alt and alt != prepared.english_query:
                vector_queries.append(alt)

        seen_queries: set[str] = set()
        for vq in vector_queries:
            vq = vq.strip()
            if not vq or vq in seen_queries:
                continue
            seen_queries.add(vq)
            try:
                pairs = self._vector_store.similarity_search_with_score(vq, k=vector_n)
                ranked_lists.append(list(pairs))
            except Exception as exc:
                logger.warning("Vector search failed for query=%r: %s", vq[:80], exc)

        # ---- BM25 / sparse retrieval ----
        bm25_terms: list[str] = []
        if prepared.keywords:
            bm25_terms.extend(prepared.keywords)
        bm25_terms.append(prepared.english_query)
        bm25_query = " ".join(bm25_terms)
        try:
            bm25_results = self._bm25.search(bm25_query, top_k=bm25_n)
            if bm25_results:
                ranked_lists.append(list(bm25_results))
        except Exception as exc:
            logger.warning("BM25 search failed: %s", exc)

        if not ranked_lists:
            logger.warning("Hybrid retrieval: all search paths returned empty")
            return []

        # ---- RRF fusion ----
        fused = rrf_fusion(ranked_lists, k=rrf_k)
        logger.info(
            "Hybrid retrieval: vector_queries=%d bm25_terms=%d fused=%d top_k=%d",
            len(seen_queries),
            len(bm25_terms),
            len(fused),
            k,
        )

        return [_to_retrieved_chunk(doc, score) for doc, score in fused[:k]]

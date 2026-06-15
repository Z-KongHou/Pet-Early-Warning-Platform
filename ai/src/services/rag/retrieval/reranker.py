"""Reranking layer for Hybrid RAG: LLM-based relevance scoring.

Day 3 implementation per hybrid-rag-3day-plan.md.
Cross-encoder path (sentence-transformers) is planned but requires torch;
LLM reranker via DeepSeek is the practical default.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Sequence

from services.rag.retrieval.vector import RetrievedChunk

logger = logging.getLogger(__name__)

_RERANK_SYSTEM = (
    "You are a relevance ranker for a veterinary knowledge base about small pets "
    "(hamsters, etc.). Given a user question and a list of retrieved text chunks, "
    "score each chunk on how well it helps answer the question.\n"
    "Scoring rules:\n"
    "- 5: Directly answers the question with specific facts.\n"
    "- 4: Highly relevant, contains key information.\n"
    "- 3: Somewhat relevant, partially addresses the question.\n"
    "- 2: Marginally relevant, mentions related topics.\n"
    "- 1: Not relevant or off-topic.\n"
    "Output ONLY a JSON array of integers (the scores), one per chunk, in the same order. "
    "Example: [4, 2, 5, 1, 3]\n"
    "Do not include any other text."
)


class LlmReranker:
    """LLM-based relevance reranker using DeepSeek (or any OpenAI-compatible LLM).

    Sends candidate chunks to the LLM for pointwise relevance scoring,
    then returns the top-N most relevant chunks.
    """

    def __init__(self, llm=None) -> None:
        """If llm is None, lazily creates from get_chat_llm()."""
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            from clients.llm import get_chat_llm
            self._llm = get_chat_llm()
        return self._llm

    def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_n: int,
    ) -> list[RetrievedChunk]:
        """Score candidate chunks via LLM and return top-N.

        Falls back to original order if LLM call fails.
        """
        chunks = list(chunks)
        if len(chunks) <= top_n:
            return chunks

        try:
            scores = self._score_chunks(query, chunks)
        except Exception as exc:
            logger.warning("LLM rerank failed, returning original order: %s", exc)
            return chunks[:top_n]

        # Pair chunks with scores, sort descending by score
        scored = list(zip(chunks, scores))
        scored.sort(key=lambda x: -x[1])

        top = scored[:top_n]
        if not top:
            return chunks[:top_n]

        max_score = max(s for _, s in top) or 1.0
        return [
            RetrievedChunk(
                content=chunk.content,
                source=chunk.source,
                filename=chunk.filename,
                chunk_index=chunk.chunk_index,
                score=round(score / max_score, 4),  # normalize to [0,1]
            )
            for chunk, score in top
        ]

    def _score_chunks(self, query: str, chunks: Sequence[RetrievedChunk]) -> list[int]:
        """Ask LLM to score all chunks in one call."""
        chunks_text = ""
        for i, chunk in enumerate(chunks):
            excerpt = chunk.content[:400].replace("\n", " ")
            chunks_text += f"[{i}] {excerpt}\n"

        user = (
            f"Question: {query.strip()}\n\n"
            f"Chunks to score:\n{chunks_text}\n"
            "Scores (JSON array only):"
        )

        raw = self.llm.chat(_RERANK_SYSTEM, user).strip()
        scores = self._parse_scores(raw, expected=len(chunks))
        if scores is None:
            raise ValueError(f"Failed to parse LLM rerank scores from: {raw[:200]}")
        return scores

    @staticmethod
    def _parse_scores(raw: str, expected: int) -> list[int] | None:
        """Parse the LLM's JSON array response, with robust fallback."""
        from utils.parsing import parse_json_array

        parsed = parse_json_array(raw)
        if parsed and len(parsed) == expected:
            try:
                return [int(x) for x in parsed]
            except (ValueError, TypeError):
                pass

        # Last resort: extract individual numbers 1-5 from raw text
        numbers = re.findall(r"\b([1-5])\b", raw)
        if len(numbers) == expected:
            return [int(n) for n in numbers]

        return None

"""Retrieve top-k chunks from the Chroma vector store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import settings
from repositories.vector_store import VectorStoreRepository


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    source: str
    filename: str
    chunk_index: int | None
    score: float


class RagRetriever:
    """Similarity search over embedded knowledge chunks."""

    def __init__(self, vector_store: VectorStoreRepository) -> None:
        self._store = vector_store

    def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        question = query.strip()
        if not question:
            raise ValueError("Question must not be empty")

        if self._store.count() == 0:
            raise ValueError("Knowledge base is empty; run POST /api/rag/ingest first")

        k = top_k or settings.rag_top_k
        pairs = self._store.similarity_search_with_score(question, k=k)

        chunks: list[RetrievedChunk] = []
        for doc, score in pairs:
            if score > settings.rag_max_distance:
                continue
            meta = doc.metadata or {}
            source = str(meta.get("source", ""))
            filename = str(meta.get("filename", "")) or (Path(source).name if source else "")
            chunk_index = meta.get("chunk_index")
            if chunk_index is not None and not isinstance(chunk_index, int):
                try:
                    chunk_index = int(chunk_index)
                except (TypeError, ValueError):
                    chunk_index = None
            chunks.append(
                RetrievedChunk(
                    content=doc.page_content,
                    source=source,
                    filename=filename,
                    chunk_index=chunk_index,
                    score=float(score),
                )
            )
        return chunks

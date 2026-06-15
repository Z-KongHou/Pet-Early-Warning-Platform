"""RAG ingest pipeline: load, chunk, embed, and persist to Chroma."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document

from config import settings
from repositories.vector_store import VectorStoreRepository
from services.rag.ingest.chunking import DocumentChunker
from services.rag.ingest.loader import DocumentLoader

if TYPE_CHECKING:
    from repositories.bm25_index import Bm25IndexRepository
    from repositories.facts_repository import FactsRepository
    from services.rag.extraction.facts import FactExtractor

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    data_dir: str
    files_loaded: int
    chunks_indexed: int
    vectors_removed: int
    sources: list[str] = field(default_factory=list)


class IngestService:
    """Ingest documents from the data directory into Chroma and BM25."""

    def __init__(
        self,
        vector_store: VectorStoreRepository,
        bm25_index: Bm25IndexRepository | None = None,
        fact_extractor: FactExtractor | None = None,
        facts_repo: FactsRepository | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._bm25 = bm25_index
        self._fact_extractor = fact_extractor
        self._facts_repo = facts_repo
        self._chunker = DocumentChunker()

    def ingest_directory(
        self,
        dir_path: str | Path | None = None,
        *,
        reset_collection: bool = False,
    ) -> IngestResult:
        root = Path(dir_path) if dir_path else settings.rag_data_path
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root}")

        if reset_collection:
            self._vector_store.reset()
            if self._bm25 is not None:
                self._bm25.reset()
            if self._facts_repo is not None:
                self._facts_repo.reset()

        file_docs = DocumentLoader.load_directory(root, apply_cleaner=True)
        if not file_docs:
            logger.warning("No supported documents found in: %s", root)
            return IngestResult(
                data_dir=str(root.resolve()),
                files_loaded=0,
                chunks_indexed=0,
                vectors_removed=0,
            )

        chunks = self._chunker.chunk_documents(file_docs)

        # Replace sources in vector store
        removed = self._replace_sources(chunks)
        indexed = self._vector_store.add_documents(chunks)

        # Sync BM25 index
        bm25_indexed = 0
        if self._bm25 is not None:
            bm25_removed = self._replace_bm25_sources(chunks)
            bm25_indexed = self._bm25.add_documents(chunks)
            logger.info(
                "BM25 sync: removed=%d indexed=%d",
                bm25_removed,
                bm25_indexed,
            )

        # Async fact extraction (non-blocking, best-effort)
        if self._fact_extractor is not None and self._facts_repo is not None:
            try:
                logger.info("Starting fact extraction for %d chunks...", len(chunks))
                facts = self._fact_extractor.extract_from_chunks(chunks)
                if facts:
                    self._facts_repo.insert(facts)
                    logger.info("Fact extraction complete: %d facts stored", len(facts))
                else:
                    logger.info("Fact extraction: no facts found")
            except Exception as exc:
                logger.warning("Fact extraction failed (non-blocking): %s", exc)

        sources = sorted(
            {str(doc.metadata.get("source", "")) for doc in file_docs if doc.metadata.get("source")}
        )
        logger.info(
            "RAG ingest complete: dir=%s files=%d chunks=%d removed=%d",
            root,
            len(file_docs),
            indexed,
            removed,
        )
        return IngestResult(
            data_dir=str(root.resolve()),
            files_loaded=len(file_docs),
            chunks_indexed=indexed,
            vectors_removed=removed,
            sources=sources,
        )

    def _replace_sources(self, chunks: list[Document]) -> int:
        sources = {str(c.metadata.get("source", "")) for c in chunks}
        removed = 0
        for source in sources:
            if source:
                removed += self._vector_store.delete_by_source(source)
        return removed

    def _replace_bm25_sources(self, chunks: list[Document]) -> int:
        """Remove existing BM25 entries for the same sources before re-adding."""
        if self._bm25 is None:
            return 0
        sources = {str(c.metadata.get("source", "")) for c in chunks}
        removed = 0
        for source in sources:
            if source:
                removed += self._bm25.delete_by_source(source)
        return removed

    def collection_stats(self) -> dict[str, int | str]:
        return {
            "collection": self._vector_store.collection_name,
            "document_count": self._vector_store.count(),
            "bm25_chunk_count": self._bm25.count if self._bm25 is not None else 0,
            "facts_count": self._facts_repo.count if self._facts_repo is not None else 0,
            "persist_dir": str(settings.chroma_path.resolve()),
        }

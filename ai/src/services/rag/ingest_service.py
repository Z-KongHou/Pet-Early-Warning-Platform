"""RAG ingest pipeline: load, chunk, embed, and persist to Chroma."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.documents import Document

from config import settings
from repositories.vector_store import VectorStoreRepository
from services.rag.chunking import DocumentChunkerTransformer
from services.rag.document_loader import DocumentLoader

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    data_dir: str
    files_loaded: int
    chunks_indexed: int
    vectors_removed: int
    sources: list[str] = field(default_factory=list)


class IngestService:
    """Ingest documents from the data directory into Chroma."""

    def __init__(self, vector_store: VectorStoreRepository) -> None:
        self._vector_store = vector_store
        self._chunker = DocumentChunkerTransformer()

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

        file_docs = DocumentLoader.load_directory(root, apply_cleaner=True)
        if not file_docs:
            logger.warning("No supported documents found in: %s", root)
            return IngestResult(
                data_dir=str(root.resolve()),
                files_loaded=0,
                chunks_indexed=0,
                vectors_removed=0,
            )

        chunks = list(self._chunker.transform_documents(file_docs))
        removed = self._replace_sources(chunks)
        indexed = self._vector_store.add_documents(chunks)

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

    def collection_stats(self) -> dict[str, int | str]:
        return {
            "collection": self._vector_store.collection_name,
            "document_count": self._vector_store.count(),
            "persist_dir": str(settings.chroma_path.resolve()),
        }

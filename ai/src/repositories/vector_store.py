"""Chroma ??????????????????"""

from __future__ import annotations

import gc
import hashlib
import logging
import re
import shutil
import sqlite3
import time
from typing import Any, List, Sequence

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from config import settings

logger = logging.getLogger(__name__)

_UUID_DIR = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_CLEAR_BATCH = 5000


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Chroma ????? metadata??? None ????????????"""
    clean: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, bool):
            clean[key] = value
        elif isinstance(value, int):
            clean[key] = value
        elif isinstance(value, float):
            clean[key] = value
        elif isinstance(value, str):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def chunk_document_id(doc: Document) -> str:
    """????? + ??????? ID??????????"""
    source = str(doc.metadata.get("source", doc.page_content[:64]))
    index = doc.metadata.get("chunk_index", 0)
    digest = hashlib.sha256(f"{source}:{index}".encode("utf-8")).hexdigest()
    return digest[:32]


class VectorStoreRepository:
    """LangChain Chroma ????? PersistentClient?????? HNSW ????"""

    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings
        self._vectorstore: Chroma | None = None
        self._client = chromadb.PersistentClient(path=self._ensure_persist_dir())

    @property
    def collection_name(self) -> str:
        return settings.chroma_collection_name

    def _ensure_persist_dir(self) -> str:
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        return str(settings.chroma_path)

    @property
    def vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                client=self._client,
                collection_name=self.collection_name,
                embedding_function=self._embeddings,
            )
        return self._vectorstore

    def count(self) -> int:
        return self.vectorstore._collection.count()

    def similarity_search_with_score(
        self,
        query: str,
        *,
        k: int,
    ) -> list[tuple[Document, float]]:
        return self.vectorstore.similarity_search_with_score(query, k=k)

    def reset(self) -> None:
        """??????????????????????????? UUID ???"""
        collection = self.vectorstore._collection
        removed = 0
        while True:
            batch = collection.get(limit=_CLEAR_BATCH, include=[]).get("ids") or []
            if not batch:
                break
            collection.delete(ids=batch)
            removed += len(batch)

        gc.collect()
        pruned = self._prune_orphan_segment_dirs()
        logger.info(
            "????? %s??? %d ?????? %d ??????",
            self.collection_name,
            removed,
            pruned,
        )

    def _active_segment_ids(self) -> set[str]:
        db_file = settings.chroma_path / "chroma.sqlite3"
        if not db_file.exists():
            return set()
        try:
            with sqlite3.connect(db_file) as con:
                rows = con.execute("SELECT id FROM segments").fetchall()
            return {str(row[0]) for row in rows}
        except sqlite3.Error as exc:
            logger.debug("?? segments ???: %s", exc)
            return set()

    def _prune_orphan_segment_dirs(self, *, retries: int = 3) -> int:
        """?? chroma_db ??? segments ??? UUID ????? delete_collection ????"""
        active = self._active_segment_ids()
        persist = settings.chroma_path
        pruned = 0

        for item in list(persist.iterdir()):
            if not item.is_dir() or not _UUID_DIR.match(item.name):
                continue
            if item.name in active:
                continue
            for attempt in range(retries):
                try:
                    shutil.rmtree(item)
                    pruned += 1
                    break
                except OSError as exc:
                    if attempt + 1 >= retries:
                        logger.warning("????????? %s: %s", item, exc)
                    else:
                        time.sleep(0.2)
                        gc.collect()
        return pruned

    def delete_by_source(self, source: str) -> int:
        if not source:
            return 0
        collection = self.vectorstore._collection
        existing = collection.get(where={"source": source})
        ids = existing.get("ids") or []
        if ids:
            collection.delete(ids=ids)
        return len(ids)

    def add_documents(self, documents: Sequence[Document]) -> int:
        if not documents:
            return 0

        prepared: List[Document] = []
        ids: List[str] = []
        for doc in documents:
            prepared.append(
                Document(
                    page_content=doc.page_content,
                    metadata=sanitize_metadata(dict(doc.metadata)),
                )
            )
            ids.append(chunk_document_id(doc))

        self.vectorstore.add_documents(documents=prepared, ids=ids)
        return len(prepared)

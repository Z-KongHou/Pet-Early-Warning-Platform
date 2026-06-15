"""BM25 keyword index with jieba tokenization and pickle persistence.

Mirrors VectorStoreRepository's interface for seamless integration
into IngestService and HybridRetriever.
"""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Sequence

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from config import settings

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힯]")

_jieba_loaded = False


def _ensure_jieba_dict() -> None:
    """Lazy-load jieba with hamster custom dictionary on first tokenization."""
    global _jieba_loaded
    if _jieba_loaded:
        return
    _jieba_loaded = True
    import jieba
    dict_path = settings.base_dir / "data" / "hamster_dict.txt"
    if dict_path.exists():
        jieba.load_userdict(str(dict_path))
        logger.info("Loaded hamster custom dictionary from %s", dict_path)


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


class Bm25IndexRepository:
    """BM25 keyword search over knowledge chunks with jieba tokenization.

    Stores tokenized corpus and document list on disk via pickle,
    rebuilding the BM25Okapi index on load and after each mutation.
    """

    def __init__(self, persist_path: Path | None = None) -> None:
        self._persist_path = persist_path or (settings.chroma_path / "bm25_corpus.pkl")
        self._corpus: list[list[str]] = []  # tokenized texts
        self._docs: list[Document] = []     # parallel document store
        self._index: BM25Okapi | None = None
        self._load()

    @property
    def count(self) -> int:
        return len(self._docs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_documents(self, documents: Sequence[Document]) -> int:
        if not documents:
            return 0
        for doc in documents:
            self._corpus.append(self._tokenize(doc.page_content))
            self._docs.append(doc)
        self._rebuild_index()
        self._save()
        logger.info("BM25 index: added %d documents, total=%d", len(documents), self.count)
        return len(documents)

    def delete_by_source(self, source: str) -> int:
        if not source:
            return 0
        removed = 0
        keep_corpus: list[list[str]] = []
        keep_docs: list[Document] = []
        for tokens, doc in zip(self._corpus, self._docs):
            doc_source = str(doc.metadata.get("source", ""))
            if doc_source == source:
                removed += 1
            else:
                keep_corpus.append(tokens)
                keep_docs.append(doc)
        if removed:
            self._corpus = keep_corpus
            self._docs = keep_docs
            self._rebuild_index()
            self._save()
            logger.info("BM25 index: removed %d chunks for source=%r, total=%d", removed, source, self.count)
        return removed

    def reset(self) -> None:
        """Clear all documents from the BM25 index."""
        if not self._corpus:
            return
        n = len(self._corpus)
        self._corpus = []
        self._docs = []
        self._index = None
        self._save()
        logger.info("BM25 index: reset, removed %d chunks", n)

    def search(self, query: str, top_k: int) -> list[tuple[Document, float]]:
        """BM25 keyword search. Returns (Document, score) pairs sorted by score descending."""
        if not self._index or not query.strip():
            return []
        tokens = self._tokenize(query)
        scores = self._index.get_scores(tokens)
        # Pair (doc, score) and sort descending
        scored = sorted(
            zip(self._docs, scores, range(len(self._docs))),
            key=lambda x: (-x[1], x[2]),  # stable sort by score desc, then original order
        )
        top = scored[:top_k]
        return [(doc, float(score)) for doc, score, _idx in top if score > 0]

    # ------------------------------------------------------------------
    # Tokenization
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text for BM25 indexing.

        Uses jieba for Chinese/CJK text (handles mixed CJK+English well).
        Falls back to whitespace-split for pure English text.
        """
        text = text.strip()
        if not text:
            return []
        if _has_cjk(text):
            _ensure_jieba_dict()
            import jieba
            return [t.strip() for t in jieba.cut(text) if t.strip()]
        return text.lower().split()

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _rebuild_index(self) -> None:
        if not self._corpus:
            self._index = None
            return
        self._index = BM25Okapi(self._corpus)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "corpus": self._corpus,
            "docs": [
                {
                    "page_content": doc.page_content,
                    "metadata": dict(doc.metadata),
                }
                for doc in self._docs
            ],
        }
        with open(self._persist_path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

    def _load(self) -> None:
        if not self._persist_path.exists():
            return
        try:
            with open(self._persist_path, "rb") as f:
                data = pickle.load(f)
            self._corpus = data.get("corpus", [])
            self._docs = [
                Document(page_content=d["page_content"], metadata=d.get("metadata", {}))
                for d in data.get("docs", [])
            ]
            self._rebuild_index()
            logger.info("BM25 index loaded from %s: %d chunks", self._persist_path, self.count)
        except Exception as exc:
            logger.warning("Failed to load BM25 index from %s: %s. Starting fresh.", self._persist_path, exc)
            self._corpus = []
            self._docs = []
            self._index = None

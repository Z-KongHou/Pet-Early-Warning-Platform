"""Document chunking with LangChain built-in RecursiveCharacterTextSplitter.

Chinese + English punctuation-aware separators.  Per-document, stateless,
idempotent — safe for incremental ingest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings

# ── Separator tiers (highest → lowest priority) ──────────────────────────

# Markdown structural elements split BEFORE sentence boundaries.
_MD_STRUCTURE: list[str] = [
    "\n###### ",
    "\n##### ",
    "\n#### ",
    "\n### ",
    "\n## ",
    "\n# ",
    "```\n",
    "\n***",
    "\n---",
    "\n___",
]

# Chinese + English sentence / clause boundaries.
_SENTENCE_BOUNDARIES: list[str] = [
    "\n\n",
    "\n",
    "。",
    "？",
    "！",
    "；",
    "，",  # Chinese punctuation
    ". ",
    "? ",
    "! ",
    "; ",
    ", ",  # English punctuation
    " ",
    "",
]

MD_SEPARATORS: list[str] = [*_MD_STRUCTURE, *_SENTENCE_BOUNDARIES]
TEXT_SEPARATORS: list[str] = _SENTENCE_BOUNDARIES

MARKDOWN_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown"})


@dataclass(frozen=True)
class ChunkingConfig:
    """Chunk sizing knobs, overridable via env / settings."""

    chunk_size: int = 512
    chunk_overlap: int = 100
    min_chunk_chars: int = 50

    @classmethod
    def from_settings(cls) -> ChunkingConfig:
        return cls(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            min_chunk_chars=settings.rag_chunk_min_chars,
        )


class DocumentChunker:
    """Split Chinese / English documents with LangChain built-in splitters.

    One ``RecursiveCharacterTextSplitter`` per content family — no custom
    splitting logic, no header-metadata merge pass.
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        cfg = config or ChunkingConfig.from_settings()
        self._md_splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
            separators=MD_SEPARATORS,
        )
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
            separators=TEXT_SEPARATORS,
        )
        self._min_chunk_chars = cfg.min_chunk_chars

    # ── public API ──────────────────────────────────────────────────────

    def chunk_document(self, doc: Document) -> List[Document]:
        """Chunk a single document.  Idempotent: same input → same output."""
        if not doc.page_content or not doc.page_content.strip():
            return []

        ext = str(doc.metadata.get("extension", "")).lower()
        splitter = (
            self._md_splitter if ext in MARKDOWN_EXTENSIONS else self._text_splitter
        )
        chunks = splitter.split_documents([doc])
        return self._finalize(chunks, doc)

    def chunk_documents(self, documents: Sequence[Document]) -> List[Document]:
        return [c for doc in documents for c in self.chunk_document(doc)]

    # ── internal ────────────────────────────────────────────────────────

    def _finalize(
        self, chunks: List[Document], source: Document
    ) -> List[Document]:
        valid = [
            c
            for c in chunks
            if len(c.page_content.strip()) >= self._min_chunk_chars
        ]
        total = len(valid)
        return [
            Document(
                page_content=c.page_content.strip(),
                metadata={
                    **source.metadata,
                    **c.metadata,
                    "chunk_index": i,
                    "chunk_count": total,
                },
            )
            for i, c in enumerate(valid)
        ]

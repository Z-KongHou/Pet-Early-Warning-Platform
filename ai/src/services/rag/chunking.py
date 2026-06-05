"""Document chunking with recursive splitting and Markdown header awareness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from langchain_core.documents import Document
from langchain_core.documents.transformers import BaseDocumentTransformer
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from config import settings

ENGLISH_SEPARATORS: tuple[str, ...] = (
    "\n\n",
    "\n",
    ". ",
    "? ",
    "! ",
    "; ",
    ", ",
    " ",
    "",
)

MARKDOWN_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown"})

MARKDOWN_HEADERS: tuple[tuple[str, str], ...] = (
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
)


@dataclass(frozen=True)
class ChunkingConfig:
    """Chunk sizes tuned for nomic-embed-text and English veterinary docs."""

    chunk_size: int = 1200
    chunk_overlap: int = 200
    min_chunk_chars: int = 50

    @classmethod
    def from_settings(cls) -> ChunkingConfig:
        return cls(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            min_chunk_chars=settings.rag_chunk_min_chars,
        )


class DocumentChunker:
    """Split documents into chunks and attach chunk metadata."""

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config = config or ChunkingConfig.from_settings()

    def split_text(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []
        parts = self._recursive_splitter().split_text(text)
        return [p for p in parts if len(p.strip()) >= self._config.min_chunk_chars]

    def chunk_document(self, doc: Document) -> List[Document]:
        if not doc.page_content or not doc.page_content.strip():
            return []

        ext = str(doc.metadata.get("extension", "")).lower()
        if ext in MARKDOWN_EXTENSIONS:
            raw_chunks = self._chunk_markdown(doc)
        else:
            raw_chunks = self._recursive_splitter().split_documents([doc])

        return self._finalize_chunks(raw_chunks, doc)

    def chunk_documents(self, documents: Sequence[Document]) -> List[Document]:
        chunks: List[Document] = []
        for doc in documents:
            chunks.extend(self.chunk_document(doc))
        return chunks

    def _recursive_splitter(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            chunk_size=self._config.chunk_size,
            chunk_overlap=self._config.chunk_overlap,
            length_function=len,
            separators=list(ENGLISH_SEPARATORS),
            is_separator_regex=False,
        )

    def _chunk_markdown(self, doc: Document) -> List[Document]:
        sections = MarkdownHeaderTextSplitter(
            headers_to_split_on=list(MARKDOWN_HEADERS),
            strip_headers=False,
        ).split_text(doc.page_content)

        if not sections:
            return self._recursive_splitter().split_documents([doc])

        splitter = self._recursive_splitter()
        merged: List[Document] = []
        for section in sections:
            if len(section.page_content.strip()) <= self._config.chunk_size:
                merged.append(
                    Document(
                        page_content=section.page_content.strip(),
                        metadata={**doc.metadata, **section.metadata},
                    )
                )
            else:
                merged.extend(
                    splitter.split_documents(
                        [
                            Document(
                                page_content=section.page_content,
                                metadata={**doc.metadata, **section.metadata},
                            )
                        ]
                    )
                )
        return merged

    def _finalize_chunks(self, chunks: Sequence[Document], source: Document) -> List[Document]:
        valid = [c for c in chunks if len(c.page_content.strip()) >= self._config.min_chunk_chars]
        total = len(valid)
        result: List[Document] = []
        for index, chunk in enumerate(valid):
            metadata = {**source.metadata, **chunk.metadata}
            metadata["chunk_index"] = index
            metadata["chunk_count"] = total
            result.append(
                Document(
                    page_content=chunk.page_content.strip(),
                    metadata=metadata,
                )
            )
        return result


class DocumentChunkerTransformer(BaseDocumentTransformer):
    """LangChain transformer that applies DocumentChunker to each document."""

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._chunker = DocumentChunker(config=config)

    def transform_documents(
        self,
        documents: Sequence[Document],
        **kwargs: object,
    ) -> Sequence[Document]:
        return self._chunker.chunk_documents(documents)

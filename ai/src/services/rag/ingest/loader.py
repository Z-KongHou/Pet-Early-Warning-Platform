"""LangChain document loaders with TextCleaner post-processing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Sequence

from langchain_community.document_loaders import (
    BSHTMLLoader,
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from services.rag.ingest.cleaner import SUPPORTED_EXTENSIONS, TextCleanerTransformer

logger = logging.getLogger(__name__)

_UTF8 = "utf-8"


class DocumentLoader:
    """Load supported files via LangChain loaders."""

    _cleaner = TextCleanerTransformer()

    @staticmethod
    def loader_for(file_path: str | Path) -> BaseLoader | None:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return None
        path_str = str(path.resolve())
        if ext == ".pdf":
            return PyPDFLoader(path_str)
        if ext in (".html", ".htm"):
            return BSHTMLLoader(
                path_str,
                open_encoding=_UTF8,
                bs_kwargs={"features": "html.parser"},
            )
        if ext == ".docx":
            return Docx2txtLoader(path_str)
        return TextLoader(path_str, encoding=_UTF8)

    @staticmethod
    def load_file(file_path: str | Path, *, apply_cleaner: bool = True) -> List[Document]:
        path = Path(file_path)
        loader = DocumentLoader.loader_for(path)
        if loader is None:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        raw_docs = loader.load()
        merged = DocumentLoader._merge_pages(raw_docs, path)
        if apply_cleaner:
            return list(DocumentLoader._cleaner.transform_documents([merged]))
        return [merged]

    @staticmethod
    def load_directory(
        dir_path: str | Path,
        *,
        apply_cleaner: bool = True,
    ) -> List[Document]:
        root = Path(dir_path)
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root}")

        documents: List[Document] = []
        for file_path in sorted(root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                documents.extend(
                    DocumentLoader.load_file(file_path, apply_cleaner=apply_cleaner)
                )
            except Exception:
                logger.exception("Failed to load file: %s", file_path)
        return documents

    @staticmethod
    def _merge_pages(docs: Sequence[Document], path: Path) -> Document:
        parts = [d.page_content.strip() for d in docs if d.page_content and d.page_content.strip()]
        base_meta: dict[str, Any] = dict(docs[0].metadata) if docs else {}
        ext = path.suffix.lower()
        return Document(
            page_content="\n\n".join(parts),
            metadata={
                **base_meta,
                "source": str(path.resolve()),
                "filename": path.name,
                "extension": ext,
            },
        )

"""LangChain document transformers and text normalization for RAG."""

from __future__ import annotations

import html as html_lib
import re
import unicodedata
from enum import Enum
from pathlib import Path
from typing import List, Pattern, Sequence, Union

from langchain_core.documents import Document
from langchain_core.documents.transformers import BaseDocumentTransformer

SourceInput = Union["SourceKind", str]

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".html", ".htm", ".txt", ".md", ".markdown", ".docx"}
)


class SourceKind(str, Enum):
    PDF = "pdf"
    HTML = "html"
    TXT = "txt"
    MARKDOWN = "markdown"
    WORD = "word"
    GENERIC = "generic"


_EXT_TO_KIND: dict[str, SourceKind] = {
    ".pdf": SourceKind.PDF,
    ".html": SourceKind.HTML,
    ".htm": SourceKind.HTML,
    ".txt": SourceKind.TXT,
    ".md": SourceKind.MARKDOWN,
    ".markdown": SourceKind.MARKDOWN,
    ".docx": SourceKind.WORD,
}

_DEFAULT_HEADER_FOOTER_PATTERNS: tuple[str, ...] = (
    r"^\s*Merck Veterinary Manual\s*$",
    r"^\s*MSD Veterinary Manual\s*$",
    r"^\s*WikiVet\s*$",
    r"^\s*All Other Pets\s*$",
    r"^\s*Copyright\s*\u00a9.*$",
    r"^\s*\u00a9\s*\d{4}.*$",
)


class TextCleaner:
    """Normalize extracted text from PDF, HTML, Markdown, and Word sources."""

    _CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    _ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2028\u2029\ufeff]")
    _HTML_TAG = re.compile(r"<[^>]+>", re.DOTALL)
    _HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
    _PDF_SOFT_HYPHEN = "\u00ad"
    _PDF_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)", re.UNICODE)
    _PDF_PAGE_LINE = re.compile(
        r"^\s*(?:page\s*)?\d{1,4}\s*(?:\s*(?:of|/)\s*\d{1,4})?\s*\.?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    _DOT_LEADER = re.compile(r"\.{4,}")
    _EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
    _LINE_ONLY_SYMBOLS = re.compile(r"^\s*[\|\-_\u2022\u00b7]{1,6}\s*$")

    @staticmethod
    def from_extension(ext: str) -> SourceKind:
        return _EXT_TO_KIND.get(ext.lower(), SourceKind.GENERIC)

    @staticmethod
    def from_document(doc: Document) -> SourceKind:
        ext = doc.metadata.get("extension")
        if ext:
            return TextCleaner.from_extension(str(ext))
        source = doc.metadata.get("source")
        if source:
            return TextCleaner.from_extension(Path(str(source)).suffix)
        return SourceKind.GENERIC

    @staticmethod
    def clean(text: str, source: SourceInput = SourceKind.GENERIC) -> str:
        """Clean text for the given source kind."""
        if not text:
            return ""

        kind = TextCleaner._resolve_kind(source)

        text = TextCleaner._normalize_unicode(text)
        text = TextCleaner._strip_control_and_zero_width(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        if kind in (SourceKind.HTML, SourceKind.PDF, SourceKind.GENERIC):
            text = TextCleaner._fix_html_artifacts(text)

        if kind is SourceKind.PDF:
            text = TextCleaner._fix_pdf_artifacts(text)
            text = TextCleaner.remove_headers_footers(text, list(_DEFAULT_HEADER_FOOTER_PATTERNS))
        elif kind is SourceKind.HTML:
            text = TextCleaner._fix_html_text_layout(text)
        elif kind is SourceKind.MARKDOWN:
            text = TextCleaner._fix_markdown_artifacts(text)
        elif kind is SourceKind.WORD:
            text = TextCleaner._fix_word_artifacts(text)

        text = TextCleaner._normalize_paragraph_whitespace(text)
        text = TextCleaner._drop_junk_lines(text, kind)
        return text.strip()

    @staticmethod
    def clean_document(doc: Document) -> Document:
        kind = TextCleaner.from_document(doc)
        return Document(
            page_content=TextCleaner.clean(doc.page_content, source=kind),
            metadata=dict(doc.metadata),
        )

    @staticmethod
    def remove_headers_footers(text: str, patterns: List[str]) -> str:
        """Drop lines matching header/footer patterns."""
        if not patterns:
            return text
        compiled: list[Pattern[str]] = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE | re.MULTILINE))
            except re.error:
                continue
        lines = text.split("\n")
        kept: list[str] = []
        for line in lines:
            if any(p.search(line) for p in compiled):
                continue
            kept.append(line)
        return "\n".join(kept)

    @staticmethod
    def _resolve_kind(source: SourceInput) -> SourceKind:
        if isinstance(source, SourceKind):
            return source
        try:
            return SourceKind(str(source).lower())
        except ValueError:
            return SourceKind.GENERIC

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        return unicodedata.normalize("NFKC", text)

    @staticmethod
    def _strip_control_and_zero_width(text: str) -> str:
        text = TextCleaner._CONTROL_CHARS.sub("", text)
        text = TextCleaner._ZERO_WIDTH.sub("", text)
        return text

    @staticmethod
    def _fix_html_artifacts(text: str) -> str:
        text = TextCleaner._HTML_COMMENT.sub("", text)
        text = TextCleaner._HTML_TAG.sub(" ", text)
        text = html_lib.unescape(text)
        return text

    @staticmethod
    def _fix_html_text_layout(text: str) -> str:
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text

    @staticmethod
    def _fix_pdf_artifacts(text: str) -> str:
        text = text.replace(TextCleaner._PDF_SOFT_HYPHEN, "")
        text = TextCleaner._PDF_HYPHEN_BREAK.sub(r"\1\2", text)
        text = TextCleaner._DOT_LEADER.sub(" ", text)
        text = re.sub(r"\t+", " ", text)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = TextCleaner._PDF_PAGE_LINE.sub("", text)
        return text

    @staticmethod
    def _fix_markdown_artifacts(text: str) -> str:
        text = re.sub(r"```[\s\S]*?```", "\n", text)
        text = re.sub(r"`[^`\n]+`", lambda m: m.group(0).strip("`"), text)
        text = TextCleaner._fix_html_artifacts(text)
        return text

    @staticmethod
    def _fix_word_artifacts(text: str) -> str:
        text = text.replace("\x0b", "\n")
        text = re.sub(r"\t+", " ", text)
        return text

    @staticmethod
    def _normalize_paragraph_whitespace(text: str) -> str:
        paragraphs = re.split(r"\n\s*\n", text)
        normalized: list[str] = []
        for block in paragraphs:
            lines = block.split("\n")
            cleaned_lines: list[str] = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line = re.sub(r"[^\S\n]+", " ", line)
                cleaned_lines.append(line)
            if cleaned_lines:
                normalized.append("\n".join(cleaned_lines))
        return "\n\n".join(normalized)

    @staticmethod
    def _drop_junk_lines(text: str, kind: SourceKind) -> str:
        lines = text.split("\n")
        kept: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                kept.append("")
                continue
            if kind is SourceKind.PDF and TextCleaner._PDF_PAGE_LINE.match(stripped):
                continue
            if TextCleaner._LINE_ONLY_SYMBOLS.match(stripped):
                continue
            if len(stripped) <= 2 and not re.search(r"[\w\u4e00-\u9fff]", stripped):
                continue
            kept.append(line)
        text = "\n".join(kept)
        return TextCleaner._EXCESS_BLANK_LINES.sub("\n\n", text)


class TextCleanerTransformer(BaseDocumentTransformer):
    """LangChain transformer that applies TextCleaner to each document."""

    def transform_documents(
        self,
        documents: Sequence[Document],
        **kwargs: object,
    ) -> Sequence[Document]:
        return [TextCleaner.clean_document(doc) for doc in documents]

"""Translate non-English RAG queries via Ollama before retrieval."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from clients.llm.ollama import build_ollama
from config import settings
from services.rag.utils.language import detect_language_code, is_english

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedQuery:
    """Prepared query for retrieval + generation.

    Day1 extension: carries rewrite artifacts even if only primary is used for vector today.
    """

    original: str
    language: str
    english_query: str  # primary for retrieval (vector)
    alternative_queries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class QueryTranslator:
    """Prepare English retrieval queries using Ollama."""

    def __init__(self) -> None:
        self._llm = build_ollama(
            model=settings.ollama_translate_model,
            temperature=settings.ollama_translate_temperature,
        )

    def prepare(self, question: str) -> PreparedQuery:
        text = question.strip()
        if not text:
            raise ValueError("Question must not be empty")

        lang = detect_language_code(text)
        if is_english(lang):
            return PreparedQuery(original=text, language="en", english_query=text)

        try:
            english = self._to_english(text, lang)
            return PreparedQuery(original=text, language=lang, english_query=english)
        except Exception as exc:
            logger.warning("Query translation failed, using original text: %s", exc)
            return PreparedQuery(original=text, language=lang, english_query=text)

    def _to_english(self, text: str, source_lang: str) -> str:
        system = (
            "You translate user questions into English for semantic search over an English knowledge base. "
            "Output ONLY valid JSON with keys language (ISO 639-1) and english_query. "
            "No markdown, no explanation."
        )
        user = (
            f"Source language hint: {source_lang}\n"
            f"User text:\n{text}\n\n"
            'JSON example: {"language":"zh","english_query":"Why is my hamster lethargic?"}'
        )
        raw = self._llm.chat(system, user)
        parsed = _parse_json_object(raw)
        english = str(parsed.get("english_query", "")).strip()
        if not english:
            raise ValueError("Translation response missing english_query")
        return english


def _parse_json_object(raw: str) -> dict:
    from utils.parsing import parse_json_object
    result = parse_json_object(raw)
    if not result:
        raise ValueError(f"Failed to parse translation JSON: {raw[:200]}")
    return result

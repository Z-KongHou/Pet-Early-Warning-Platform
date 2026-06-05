"""Translate non-English RAG queries via Ollama before retrieval."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from clients.llm.ollama import build_ollama
from config import settings
from services.rag.language_detect import detect_language_code, is_english

logger = logging.getLogger(__name__)

_LANG_DISPLAY: dict[str, str] = {
    "zh": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}


@dataclass(frozen=True)
class PreparedQuery:
    original: str
    language: str
    english_query: str


class QueryTranslator:
    """Prepare English retrieval queries using Ollama."""

    def __init__(self) -> None:
        self._llm = build_ollama(
            model=settings.ollama_translate_model,
            temperature=settings.ollama_translate_temperature,
        )

    @property
    def model(self) -> str:
        return self._llm.model

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

    def translate_answer(self, answer: str, target_language: str) -> str:
        if is_english(target_language):
            return answer.strip()
        lang = target_language.lower()
        try:
            return self._from_english(answer.strip(), lang)
        except Exception as exc:
            logger.warning("Answer translation failed, using English answer: %s", exc)
            return answer.strip()

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

    def _from_english(self, text: str, target_lang: str) -> str:
        lang_name = _LANG_DISPLAY.get(target_lang, target_lang)
        system = (
            f"Translate the assistant answer into {lang_name}. "
            "Keep facts, numbers, and structure. Output ONLY the translation, no preamble."
        )
        return self._llm.chat(system, text).strip()


_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(text)
    if match:
        data = json.loads(match.group())
        if isinstance(data, dict):
            return data
    raise ValueError(f"Failed to parse translation JSON: {raw[:200]}")

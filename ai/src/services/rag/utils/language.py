"""Lightweight language detection for RAG query routing."""

from __future__ import annotations

import re

_CJK = re.compile(r"[\u4e00-\u9fff]")
_HIRAGANA_KATAKANA = re.compile(r"[\u3040-\u30ff]")
_HANGUL = re.compile(r"[\uac00-\ud7af]")
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")
_LATIN = re.compile(r"[A-Za-z]")


def detect_language_code(text: str) -> str:
    """Return ISO 639-1 code: zh, ja, ko, ru, or en."""
    sample = text.strip()
    if not sample:
        return "en"

    if _HANGUL.search(sample):
        return "ko"
    if _HIRAGANA_KATAKANA.search(sample):
        return "ja"
    if _CJK.search(sample):
        return "zh"
    if _CYRILLIC.search(sample):
        return "ru"

    latin = len(_LATIN.findall(sample))
    if latin >= max(3, len(sample) // 4):
        return "en"

    return "en"


def is_english(code: str) -> bool:
    return code.lower() in ("en", "eng")

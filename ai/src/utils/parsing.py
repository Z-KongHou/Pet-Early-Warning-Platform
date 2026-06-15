"""Shared JSON parsing utilities for LLM responses.

Avoids duplicated markdown-fence stripping and fallback regex extraction
across fact_extractor, preference_extractor, reranker, query_rewriter,
and query_translator.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────

_JSON_OBJ_RE = re.compile(r"\{[\s\S]*\}")
_JSON_ARR_RE = re.compile(r"\[[\s\S]*\]")
_MD_FENCE_RE = re.compile(r"```(?:json)?\s*")


def _strip_fences(raw: str) -> str:
    """Remove ```json ... ``` markdown fences from LLM output."""
    text = raw.strip()
    if text.startswith("```"):
        text = _MD_FENCE_RE.sub("", text, count=1)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


# ── public API ───────────────────────────────────────────────────


def parse_json_object(raw: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse LLM output that should contain a JSON object ``{...}``.

    Tries (in order):
      1. Strip markdown fences, json.loads
      2. Regex extract the first ``{...}`` block, json.loads
      3. Return *default* (or empty dict).
    """
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: find first {...} block
    match = _JSON_OBJ_RE.search(text)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    logger.debug("parse_json_object failed, returning default. raw[:200]=%r", raw[:200])
    return default if default is not None else {}


def parse_json_array(raw: str, default: list[Any] | None = None) -> list[Any]:
    """Parse LLM output that should contain a JSON array ``[...]``.

    Tries (in order):
      1. Strip markdown fences, json.loads
      2. Regex extract the first ``[...]`` block, json.loads
      3. Return *default* (or empty list).
    """
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: find first [...] block
    match = _JSON_ARR_RE.search(text)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    logger.debug("parse_json_array failed, returning default. raw[:200]=%r", raw[:200])
    return default if default is not None else []

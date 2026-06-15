"""Shared eval utilities: GoldenQuestion loading and relevance judgment.

Used by eval_rag.py, eval_embedding.py, and analyze_distances.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.rag.retrieval.vector import RetrievedChunk


@dataclass
class GoldenQuestion:
    question: str
    difficulty: str
    lang: str
    expected_sources: list[str]
    expected_keywords: list[str]
    is_multiturn: bool = False
    previous_turns: list[dict[str, str]] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GoldenQuestion:
        return cls(
            question=d["question"],
            difficulty=d.get("difficulty", "unknown"),
            lang=d.get("lang", "zh"),
            expected_sources=d.get("expected_sources", []),
            expected_keywords=[k.lower() for k in d.get("expected_keywords", [])],
            is_multiturn=d.get("is_multiturn", False),
            previous_turns=d.get("previous_turns"),
        )


def load_questions(path: Path) -> list[GoldenQuestion]:
    qs: list[GoldenQuestion] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            qs.append(GoldenQuestion.from_dict(json.loads(line)))
    return qs


def is_relevant(chunk: RetrievedChunk, q: GoldenQuestion) -> bool:
    """A chunk is relevant if its source filename matches expected or content hits keywords."""
    src = (chunk.source or "").lower()
    fname = (chunk.filename or "").lower()
    content = (chunk.content or "").lower()

    for exp in q.expected_sources:
        if exp.lower() in src or exp.lower() in fname:
            return True
    for kw in q.expected_keywords:
        if kw in content:
            return True
    return False

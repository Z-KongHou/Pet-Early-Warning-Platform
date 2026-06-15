"""Lightweight greeting detector for RAG query fast path.

Avoids wasting LLM tokens on simple greetings / small-talk that need no retrieval.
"""

from __future__ import annotations

import re

# ── Greeting / small-talk patterns ──
_GREETING_PATTERNS = [
    r"^(你好|您好|hi|hello|hey)[\s!！。.,，]*$",
    r"^(谢谢|thanks|thank you|谢啦|多谢|感谢)[\s!！。.,，]*$",
    r"^(再见|bye|拜拜|晚安|早安)[\s!！。.,，]*$",
    r"^(你是谁|你能做什么|你叫什么|你的名字)[\s?？!！。]*$",
    r"^[\s!！。.,，?!？]*$",  # empty/punctuation only
]


def is_greeting(text: str) -> bool:
    """Check if the input is a greeting, thanks, or simple chat that needs no retrieval."""
    stripped = text.strip().lower()
    if len(stripped) >= 30:
        return False
    return any(re.match(pat, stripped, re.IGNORECASE) for pat in _GREETING_PATTERNS)

"""Multi-turn RAG chat history: truncation and retrieval query rewriting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from config import settings

ChatRole = Literal["user", "assistant"]


@dataclass(frozen=True)
class ChatTurn:
    role: ChatRole
    content: str


def estimate_tokens(text: str) -> int:
    """Rough token estimate for mixed CJK/Latin text without tiktoken."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return max(1, int(cjk / 1.5 + other / 4))


def truncate_history(
    history: Sequence[ChatTurn],
    *,
    max_turns: int | None = None,
    max_tokens: int | None = None,
) -> list[ChatTurn]:
    """Keep recent turns within max turn count and token budget."""
    if not history:
        return []

    turns = max_turns if max_turns is not None else settings.rag_chat_max_turns
    tokens = max_tokens if max_tokens is not None else settings.rag_chat_max_history_tokens

    items = list(history)
    max_messages = max(1, turns) * 2
    if len(items) > max_messages:
        items = items[-max_messages:]

    kept: list[ChatTurn] = []
    total = 0
    for msg in reversed(items):
        content = msg.content.strip()
        if not content:
            continue
        cost = estimate_tokens(content) + 4
        if total + cost > tokens and kept:
            break
        total += cost
        kept.insert(0, ChatTurn(role=msg.role, content=content))
    return kept


def format_history_for_prompt(history: Sequence[ChatTurn]) -> str:
    if not history:
        return ""
    blocks: list[str] = []
    for msg in history:
        label = "User" if msg.role == "user" else "Assistant"
        blocks.append(f"{label}: {msg.content}")
    return "Prior conversation (for follow-up context only):\n\n" + "\n\n".join(blocks)



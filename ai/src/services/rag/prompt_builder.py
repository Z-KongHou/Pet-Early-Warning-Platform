"""RAG prompt assembly for grounded LLM answers."""

from __future__ import annotations

from dataclasses import dataclass

from services.rag.chat_history import ChatTurn, format_history_for_prompt
from services.rag.language_detect import is_english
from services.rag.retriever import RetrievedChunk

_REPLY_LANGUAGE_NAMES: dict[str, str] = {
    "zh": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}


@dataclass(frozen=True)
class RagPrompt:
    system: str
    user: str


def build_rag_prompt(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    history: list[ChatTurn] | None = None,
    reply_language: str | None = None,
    answer_in_english: bool | None = None,
) -> RagPrompt:
    context_blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.filename or chunk.source or "unknown"
        header = f"[{index}] {source}"
        if chunk.chunk_index is not None:
            header += f" (chunk {chunk.chunk_index})"
        context_blocks.append(f"{header}\n{chunk.content}")

    context_text = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no context retrieved)"

    if answer_in_english is True:
        language_rule = "Reply in English only. "
    elif reply_language and not is_english(reply_language):
        lang_name = _REPLY_LANGUAGE_NAMES.get(reply_language.lower(), reply_language)
        language_rule = f"Reply in {lang_name}. The context may be in English; translate facts accurately. "
    else:
        language_rule = "Reply in the same language as the user's question. "
    system = (
        "You are a veterinary knowledge assistant for small pets (e.g. hamsters). "
        "Answer using ONLY the provided context excerpts. "
        "Prior conversation messages, if any, are only to resolve follow-up references "
        "(e.g. pronouns); ground every factual claim ONLY in the Context excerpts below. "
        "Do not treat earlier assistant replies as verified facts. "
        "If the context does not contain enough information, say so clearly and "
        "recommend consulting a licensed veterinarian. "
        f"{language_rule}"
        "Be concise, practical, and avoid making up facts."
    )

    history_block = format_history_for_prompt(history or [])
    history_prefix = f"{history_block}\n\n" if history_block else ""

    user = (
        f"{history_prefix}"
        f"Context excerpts:\n\n{context_text}\n\n"
        f"User question:\n{question.strip()}\n\n"
        "Answer:"
    )

    return RagPrompt(system=system, user=user)

"""DeepSeek-powered query rewriting for Hybrid RAG.

Responsibilities (Day1):
- Coreference resolution against recent history (it/它/this/这个/刚才...)
- Produce a clean primary English retrieval query (for vector)
- Generate 1-2 alternative queries for expanded vector recall
- Extract high-value keywords for BM25 (symptoms, diseases, english terms, product names)

The rewriter is used ONLY for retrieval preparation. Generation prompt still receives raw history.
Fallback strategy lives in QueryService._prepare_query.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from clients.llm import get_chat_llm
from config import settings
from services.rag.utils.history import ChatTurn, truncate_history
from services.rag.utils.language import detect_language_code

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RewrittenQuery:
    """Structured output of query rewrite."""

    primary_query: str
    alternative_queries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    # Optional: the language of the *original* user question
    original_language: str = "en"


class QueryRewriter:
    """Call DeepSeek (or configured LLM) to rewrite the user question for better retrieval."""

    def __init__(self) -> None:
        self._llm = get_chat_llm()
        self._max_alts = max(1, min(settings.rag_query_rewrite_max_queries or 3, 5))

    def rewrite(self, question: str, history: list[ChatTurn] | None = None) -> RewrittenQuery:
        text = (question or "").strip()
        if not text:
            raise ValueError("Question must not be empty")

        hist = truncate_history(history or [], max_turns=4, max_tokens=1200)
        lang = detect_language_code(text)

        system = (
            "You are an expert retrieval query rewriter for a veterinary RAG system about hamsters (仓鼠). "
            "Your job is to improve recall over an English veterinary knowledge base (PDFs/manuals).\n\n"
            "Rules:\n"
            "1. Resolve coreferences using the provided conversation history (e.g. '它'/'it'/'这个'/'刚才' must be expanded to the specific subject like '仓鼠湿尾症' or 'hamster wet tail').\n"
            "2. Output a primary English query optimized for semantic vector search (concise, specific, include key symptoms/disease names in English when known).\n"
            "3. Also produce up to {max_alts} short alternative English phrasings (synonyms, common lay terms, or more specific veterinary terms).\n"
            "4. Extract 4-8 high-precision keywords/phrases for keyword/BM25 retrieval. Prefer English disease names, symptoms, and important Chinese terms if they appear in the KB. Dedup.\n"
            "5. If the question is already clear, still provide 1-2 light alts and good keywords.\n"
            "6. Never invent facts; stay faithful to the user's intent.\n\n"
            "Respond with ONLY a single valid JSON object. No markdown fences, no prose."
        ).format(max_alts=self._max_alts)

        hist_block = ""
        if hist:
            lines = []
            for t in hist:
                role = "User" if t.role == "user" else "Assistant"
                c = t.content.strip()
                if len(c) > 280:
                    c = c[:280] + "..."
                lines.append(f"{role}: {c}")
            hist_block = "Recent conversation:\n" + "\n".join(lines) + "\n\n"

        user = (
            f"{hist_block}"
            f"Current user question (lang={lang}):\n{text}\n\n"
            'JSON schema example:\n'
            '{"primary_query": "hamster wet tail symptoms and treatment", '
            '"alternative_queries": ["hamster proliferative ileitis", "仓鼠湿尾症治疗"], '
            '"keywords": ["wet tail", "proliferative ileitis", "Lawsonia", "diarrhea", "dehydration", "wet tail treatment"]}'
        )

        raw = self._llm.chat(system, user)
        parsed = self._parse_json(raw)
        primary = str(parsed.get("primary_query", "")).strip()
        if not primary:
            # graceful degradation
            primary = text if lang == "en" else text  # will be translated later in fallback anyway

        alts = [str(x).strip() for x in parsed.get("alternative_queries", []) if str(x).strip()]
        alts = alts[: self._max_alts]
        kws = [str(x).strip() for x in parsed.get("keywords", []) if str(x).strip()]

        # de-dup while preserving order
        seen = set()
        clean_kws: list[str] = []
        for k in kws:
            kl = k.lower()
            if kl not in seen:
                seen.add(kl)
                clean_kws.append(k)

        return RewrittenQuery(
            primary_query=primary,
            alternative_queries=alts,
            keywords=clean_kws,
            original_language=lang,
        )

    def _parse_json(self, raw: str) -> dict:
        from utils.parsing import parse_json_object
        result = parse_json_object(raw, default={})
        if not result:
            logger.warning("QueryRewriter failed to parse JSON, raw head: %s", raw[:200])
        return result

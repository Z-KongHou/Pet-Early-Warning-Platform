"""RAG query orchestration: retrieve context and generate LLM answers.

Architecture (layered fallback):
  1. Greeting fast path   – regex-based, 0 LLM tokens, instant
  2. Agent mode           – LLM-driven tool-calling (primary)
  3. Fixed pipeline       – deterministic retrieve→rerank→generate (fallback)
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from clients.llm import get_chat_llm
from config import settings
from services.rag.routing.router import is_greeting
from services.rag.generation.validator import AnswerValidator
from services.rag.utils.history import ChatTurn, truncate_history
from services.rag.utils.language import detect_language_code
from services.rag.generation.prompt import build_rag_prompt
from services.rag.retrieval.rewriter import QueryRewriter
from services.rag.retrieval.translator import PreparedQuery, QueryTranslator
from services.rag.retrieval.vector import RagRetriever, RetrievedChunk

if TYPE_CHECKING:
    from repositories.facts_repository import FactsRepository
    from repositories.preference_repository import PreferenceRepository
    from services.rag.agent.loop import AgentLoop
    from services.rag.extraction.preferences import PreferenceExtractor
    from services.rag.retrieval.hybrid import HybridRetriever
    from services.rag.retrieval.reranker import LlmReranker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceCitation:
    source: str
    filename: str
    chunk_index: int | None
    excerpt: str
    score: float


@dataclass(frozen=True)
class QueryResult:
    question: str
    answer: str
    sources: list[SourceCitation]
    llm_model: str
    detected_language: str = "en"
    english_question: str | None = None


class QueryService:
    def __init__(
        self,
        retriever: RagRetriever,
        translator: QueryTranslator | None = None,
        rewriter: QueryRewriter | None = None,
        hybrid_retriever: HybridRetriever | None = None,
        reranker: LlmReranker | None = None,
        facts_repo: FactsRepository | None = None,
        prefs_repo: PreferenceRepository | None = None,
        pref_extractor: PreferenceExtractor | None = None,
        agent_loop: AgentLoop | None = None,
    ) -> None:
        self._retriever = retriever
        self._translator = translator
        self._rewriter = rewriter
        self._hybrid_retriever = hybrid_retriever
        self._reranker = reranker
        self._facts_repo = facts_repo
        self._prefs_repo = prefs_repo
        self._pref_extractor = pref_extractor
        self._validator = AnswerValidator()
        self._agent_loop = agent_loop

    # ── Public API ──────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        history: list[ChatTurn] | None = None,
    ) -> QueryResult:
        chat_history = self._normalize_history(history)
        self._reset_timings()

        # ── Layer 1: Greeting fast path ──
        if is_greeting(question):
            return self._direct_reply(question)

        # ── Layer 2: Agent mode (primary) ──
        if settings.rag_agent_enabled and self._agent_loop is not None:
            try:
                return self._ask_via_agent(question, chat_history)
            except Exception as exc:
                logger.warning(
                    "Agent mode failed, falling back to pipeline: %s", exc
                )

        # ── Layer 3: Fixed pipeline (fallback) ──
        return self._pipeline_ask(question, chat_history, top_k=top_k)

    def ask_stream(
        self,
        question: str,
        *,
        top_k: int | None = None,
        history: list[ChatTurn] | None = None,
    ) -> Iterator[tuple[str, dict]]:
        chat_history = self._normalize_history(history)
        self._reset_timings()

        # ── Layer 1: Greeting fast path ──
        if is_greeting(question):
            yield from self._direct_reply_stream(question)
            return

        # ── Layer 2: Agent mode (primary) ──
        if settings.rag_agent_enabled and self._agent_loop is not None:
            try:
                yield from self._ask_via_agent_stream(question, chat_history)
                return
            except Exception as exc:
                logger.warning(
                    "Agent stream failed, falling back to pipeline: %s", exc
                )

        # ── Layer 3: Fixed pipeline (fallback) ──
        yield from self._pipeline_ask_stream(question, chat_history, top_k=top_k)

    # ── Layer 1: Greeting ───────────────────────────────────────────

    @staticmethod
    def _direct_reply(question: str) -> QueryResult:
        llm = get_chat_llm()
        answer = llm.chat(
            "You are a friendly veterinary assistant for small pets. Be warm and concise.",
            question.strip(),
        )
        return QueryResult(
            question=question,
            answer=answer,
            sources=[],
            llm_model=llm.model,
            detected_language=detect_language_code(question),
        )

    @staticmethod
    def _direct_reply_stream(question: str) -> Iterator[tuple[str, dict]]:
        llm = get_chat_llm()
        lang = detect_language_code(question)
        meta = {
            "question": question,
            "sources": [],
            "llm_model": llm.model,
            "detected_language": lang,
            "english_question": None,
        }
        yield "meta", meta
        parts: list[str] = []
        for delta in llm.stream_chat(
            "You are a friendly veterinary assistant for small pets. Be warm and concise.",
            question.strip(),
        ):
            parts.append(delta)
            yield "delta", {"text": delta}
        answer = "".join(parts)
        yield "done", {**meta, "answer": answer}

    # ── Layer 2: Agent mode ─────────────────────────────────────────

    def _ask_via_agent(
        self, question: str, history: list[ChatTurn]
    ) -> QueryResult:
        t0 = time.perf_counter()
        result = self._agent_loop.run(question, history)
        dur_total = (time.perf_counter() - t0) * 1000

        import re
        refs = re.findall(r"\[(\d+)\]", result.answer)
        max_ref = max(int(r) for r in refs) if refs else 0
        self._validator.validate(result.answer, num_sources=max_ref)

        self._maybe_extract_prefs(question, result.answer, history)

        tool_names = [t.name for t in result.tool_calls]
        logger.info(
            "agent_query completed: iterations=%d tools=%s dur=%.1fms answer_len=%d",
            result.iterations,
            tool_names,
            dur_total,
            len(result.answer),
        )

        return QueryResult(
            question=question,
            answer=result.answer,
            sources=[],
            llm_model=get_chat_llm().model,
            detected_language=result.detected_language,
        )

    def _ask_via_agent_stream(
        self, question: str, history: list[ChatTurn]
    ) -> Iterator[tuple[str, dict]]:
        lang = detect_language_code(question)
        llm_model = get_chat_llm().model

        yield "meta", {
            "question": question,
            "sources": [],
            "llm_model": llm_model,
            "detected_language": lang,
            "english_question": None,
        }

        t0 = time.perf_counter()
        result = self._agent_loop.run(question, history)
        dur_total = (time.perf_counter() - t0) * 1000

        answer = result.answer
        chunk_size = 4
        for i in range(0, len(answer), chunk_size):
            yield "delta", {"text": answer[i : i + chunk_size]}

        import re
        refs = re.findall(r"\[(\d+)\]", answer)
        max_ref = max(int(r) for r in refs) if refs else 0
        self._validator.validate(answer, num_sources=max_ref)
        self._maybe_extract_prefs(question, answer, history)

        tool_names = [t.name for t in result.tool_calls]
        logger.info(
            "agent_query_stream completed: iterations=%d tools=%s dur=%.1fms answer_len=%d",
            result.iterations,
            tool_names,
            dur_total,
            len(answer),
        )

        yield "done", {
            "question": question,
            "answer": answer,
            "sources": [],
            "llm_model": llm_model,
            "detected_language": lang,
            "english_question": None,
        }

    # ── Layer 3: Fixed pipeline (fallback) ──────────────────────────

    def _pipeline_ask(
        self,
        question: str,
        history: list[ChatTurn],
        *,
        top_k: int | None = None,
    ) -> QueryResult:
        """Deterministic retrieve→rerank→generate pipeline.

        Used as fallback when agent mode is disabled or fails.
        """
        t0 = time.perf_counter()
        prepared = self._prepare_query(question, history)
        dur_rewrite = getattr(self, "_last_rewrite_ms", 0.0)

        t1 = time.perf_counter()
        chunks = self._retrieve(prepared, top_k=top_k)
        dur_retrieve = (time.perf_counter() - t1) * 1000

        if not chunks:
            self._log_structured(
                "rag_query",
                prepared=prepared,
                history_len=len(history),
                chunks=0,
                chunks_before_rerank=0,
                empty=True,
                dur_rewrite=dur_rewrite,
                dur_retrieve=dur_retrieve,
                dur_rerank=0.0,
                dur_generate=0.0,
            )
            raise ValueError("No relevant knowledge found; run POST /api/rag/ingest first")

        dur_rerank = 0.0
        chunks_before_rerank = len(chunks)
        if settings.rag_rerank_enabled and self._reranker is not None:
            t_rk = time.perf_counter()
            chunks = self._reranker.rerank(
                prepared.original, chunks, top_n=settings.rag_rerank_top_n
            )
            dur_rerank = (time.perf_counter() - t_rk) * 1000

        matched_facts = self._lookup_facts(prepared.original)
        prefs_text = self._load_prefs_text()

        llm = get_chat_llm()
        prompt = build_rag_prompt(
            prepared.original,
            chunks,
            history=history,
            reply_language=prepared.language,
            facts=matched_facts if matched_facts else None,
            prefs_text=prefs_text,
        )

        t2 = time.perf_counter()
        answer = llm.chat(prompt.system, prompt.user)
        dur_generate = (time.perf_counter() - t2) * 1000

        self._validator.validate(answer, len(chunks))
        self._maybe_extract_prefs(prepared.original, answer, history)

        self._log_structured(
            "rag_query",
            prepared=prepared,
            history_len=len(history),
            chunks=len(chunks),
            chunks_before_rerank=chunks_before_rerank,
            empty=False,
            dur_rewrite=dur_rewrite,
            dur_retrieve=dur_retrieve,
            dur_rerank=dur_rerank,
            dur_generate=dur_generate,
        )

        return QueryResult(
            question=prepared.original,
            answer=answer,
            sources=[self._to_citation(chunk) for chunk in chunks],
            llm_model=llm.model,
            detected_language=prepared.language,
            english_question=(
                prepared.english_query
                if prepared.english_query != prepared.original
                else None
            ),
        )

    def _pipeline_ask_stream(
        self,
        question: str,
        history: list[ChatTurn],
        *,
        top_k: int | None = None,
    ) -> Iterator[tuple[str, dict]]:
        """Streaming variant of the fixed pipeline."""
        t0 = time.perf_counter()
        prepared = self._prepare_query(question, history)
        dur_rewrite = getattr(self, "_last_rewrite_ms", 0.0)

        t1 = time.perf_counter()
        chunks = self._retrieve(prepared, top_k=top_k)
        dur_retrieve = (time.perf_counter() - t1) * 1000

        if not chunks:
            self._log_structured(
                "rag_query_stream",
                prepared=prepared,
                history_len=len(history),
                chunks=0,
                chunks_before_rerank=0,
                empty=True,
                dur_rewrite=dur_rewrite,
                dur_retrieve=dur_retrieve,
                dur_rerank=0.0,
                dur_generate=0.0,
            )
            yield "error", {
                "message": "No relevant knowledge found; run POST /api/rag/ingest first",
                "code": 40001,
            }
            return

        dur_rerank = 0.0
        chunks_before_rerank = len(chunks)
        if settings.rag_rerank_enabled and self._reranker is not None:
            t_rk = time.perf_counter()
            chunks = self._reranker.rerank(
                prepared.original, chunks, top_n=settings.rag_rerank_top_n
            )
            dur_rerank = (time.perf_counter() - t_rk) * 1000

        matched_facts = self._lookup_facts(prepared.original)
        prefs_text = self._load_prefs_text()

        llm = get_chat_llm()
        prompt = build_rag_prompt(
            prepared.original,
            chunks,
            history=history,
            reply_language=prepared.language,
            facts=matched_facts if matched_facts else None,
            prefs_text=prefs_text,
        )
        citations = [self._to_citation(chunk) for chunk in chunks]
        english_question = (
            prepared.english_query
            if prepared.english_query != prepared.original
            else None
        )

        self._log_structured(
            "rag_query_stream",
            prepared=prepared,
            history_len=len(history),
            chunks=len(chunks),
            chunks_before_rerank=chunks_before_rerank,
            empty=False,
            dur_rewrite=dur_rewrite,
            dur_retrieve=dur_retrieve,
            dur_rerank=dur_rerank,
            dur_generate=0.0,
        )

        yield "meta", {
            "question": prepared.original,
            "sources": [asdict(c) for c in citations],
            "llm_model": llm.model,
            "detected_language": prepared.language,
            "english_question": english_question,
        }

        t2 = time.perf_counter()
        parts: list[str] = []
        for delta in llm.stream_chat(prompt.system, prompt.user):
            parts.append(delta)
            yield "delta", {"text": delta}
        dur_generate = (time.perf_counter() - t2) * 1000

        answer = "".join(parts)

        self._validator.validate(answer, len(chunks))
        self._maybe_extract_prefs(prepared.original, answer, history)

        self._log_structured(
            "rag_query_stream_done",
            prepared=prepared,
            history_len=len(history),
            chunks=len(chunks),
            chunks_before_rerank=chunks_before_rerank,
            empty=False,
            dur_rewrite=dur_rewrite,
            dur_retrieve=dur_retrieve,
            dur_rerank=dur_rerank,
            dur_generate=dur_generate,
        )

        yield "done", {
            "question": prepared.original,
            "answer": answer,
            "sources": [asdict(c) for c in citations],
            "llm_model": llm.model,
            "detected_language": prepared.language,
            "english_question": english_question,
        }

    # ── Shared helpers ──────────────────────────────────────────────

    @staticmethod
    def _normalize_history(history: list[ChatTurn] | None) -> list[ChatTurn]:
        if not history:
            return []
        return truncate_history(history)

    def _retrieve(
        self, prepared: PreparedQuery, *, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        """Retrieve chunks, preferring hybrid when enabled and available."""
        if settings.rag_hybrid_enabled and self._hybrid_retriever is not None:
            return self._hybrid_retriever.retrieve(prepared, top_k=top_k)
        return self._retriever.retrieve(prepared.english_query, top_k=top_k)

    def _lookup_facts(self, question: str) -> list[dict]:
        if self._facts_repo is None:
            return []
        try:
            return self._facts_repo.search(question, limit=8)
        except Exception as exc:
            logger.warning("Facts lookup failed: %s", exc)
            return []

    def _prepare_query(
        self, question: str, history: list[ChatTurn]
    ) -> PreparedQuery:
        """Prepare the retrieval query.

        Retrieval NEVER receives concatenated history (avoids signal dilution).
        History is used only for:
          - QueryRewriter coreference resolution (DeepSeek)
          - Generation prompt (via build_rag_prompt)

        Three-layer fallback:
          1. If rewriter enabled & present -> use it (primary + alts + keywords)
          2. On failure or disabled, simple pronoun fallback
          3. Then (optional) legacy translator on the final retrieval_text
        """
        text = question.strip()
        if not text:
            raise ValueError("Question must not be empty")

        lang = detect_language_code(text)
        retrieval_text = text
        alts: list[str] = []
        kws: list[str] = []
        rewrite_applied = False

        # Layer 1: DeepSeek Rewriter (coref + multi + keywords)
        if settings.rag_query_rewrite_enabled and self._rewriter is not None:
            t0 = time.perf_counter()
            try:
                rewritten = self._rewriter.rewrite(text, history)
                retrieval_text = rewritten.primary_query or text
                alts = rewritten.alternative_queries or []
                kws = rewritten.keywords or []
                rewrite_applied = True
                dur = (time.perf_counter() - t0) * 1000
                logger.info(
                    "query_rewrite ok primary=%r alts=%d kws=%d dur=%.1fms",
                    retrieval_text[:80],
                    len(alts),
                    len(kws),
                    dur,
                )
                self._last_rewrite_ms = dur
            except Exception as exc:
                self._last_rewrite_ms = (time.perf_counter() - t0) * 1000
                logger.warning("Query rewrite failed, falling back: %s", exc)

        # Layer 2: minimal pronoun/coref fallback when rewrite was not applied
        if not rewrite_applied:
            retrieval_text = (
                self._apply_simple_coref_fallback(text, history) or text
            )

        # Layer 3: optional legacy translator
        if settings.rag_query_translation_enabled and self._translator is not None:
            try:
                t0 = time.perf_counter()
                prepared = self._translator.prepare(retrieval_text)
                dur = (time.perf_counter() - t0) * 1000
                self._last_translate_ms = dur
                return PreparedQuery(
                    original=text,
                    language=lang,
                    english_query=prepared.english_query,
                    alternative_queries=alts,
                    keywords=kws,
                )
            except Exception as exc:
                logger.warning("Legacy translator failed during prepare: %s", exc)

        return PreparedQuery(
            original=text,
            language=lang,
            english_query=retrieval_text,
            alternative_queries=alts,
            keywords=kws,
        )

    @staticmethod
    def _apply_simple_coref_fallback(
        text: str, history: list[ChatTurn]
    ) -> str | None:
        """Very lightweight fallback for obvious follow-ups when rewriter is off."""
        if not history:
            return None
        lowered = text.lower()
        coref_markers = (
            "它", "这个", "这个病", "这种", "刚才", "它严重",
            "it", "this", "that", "the above",
        )
        if not any(m in lowered for m in coref_markers):
            return None
        for turn in reversed(history):
            if turn.role == "user" and turn.content.strip():
                prev = turn.content.strip()
                if len(prev) > 120:
                    prev = prev[:120] + "..."
                return f"{prev}\n{text}"
        return None

    def _load_prefs_text(self) -> str:
        if self._prefs_repo is None:
            return ""
        try:
            return self._prefs_repo.format_for_prompt()
        except Exception as exc:
            logger.warning("Failed to load preferences: %s", exc)
            return ""

    def _maybe_extract_prefs(
        self, question: str, answer: str, history: list[ChatTurn]
    ) -> None:
        """Best-effort async extraction of user prefs from the current exchange."""
        if self._pref_extractor is None or self._prefs_repo is None:
            return

        def _extract():
            try:
                lines: list[str] = []
                for turn in history[-6:]:
                    role_label = "User" if turn.role == "user" else "Assistant"
                    lines.append(f"{role_label}: {turn.content[:500]}")
                lines.append(f"User: {question[:500]}")
                lines.append(f"Assistant: {answer[:500]}")
                conversation = "\n".join(lines)

                existing_pets = self._prefs_repo.get_pets()
                result = self._pref_extractor.extract(conversation, existing_pets)

                prefs = result.get("preferences", {})
                if prefs:
                    filtered = {k: v for k, v in prefs.items() if v}
                    self._prefs_repo.merge_prefs(filtered)

                pets = result.get("pets", [])
                for pet in pets:
                    if pet.get("name"):
                        self._prefs_repo.upsert_pet(pet)
                        logger.info("Upserted pet profile: %s", pet.get("name"))

                if prefs or pets:
                    logger.info(
                        "Preference extraction: %d prefs, %d pets",
                        len(prefs), len(pets),
                    )
            except Exception as exc:
                logger.warning("Preference extraction failed: %s", exc)

        threading.Thread(target=_extract, daemon=True).start()

    def _reset_timings(self) -> None:
        self._last_rewrite_ms: float = 0.0
        self._last_translate_ms: float = 0.0

    def _log_structured(
        self,
        event: str,
        *,
        prepared: PreparedQuery,
        history_len: int,
        chunks: int,
        chunks_before_rerank: int = 0,
        empty: bool,
        dur_rewrite: float,
        dur_retrieve: float,
        dur_rerank: float = 0.0,
        dur_generate: float,
    ) -> None:
        rerank_active = bool(settings.rag_rerank_enabled and self._reranker)
        logger.info(
            "%s completed",
            event,
            extra={
                "event": event,
                "chunks_retrieved": chunks,
                "chunks_before_rerank": chunks_before_rerank,
                "empty_retrieval": empty,
                "language": prepared.language,
                "history_turns": history_len,
                "rewrite_enabled": bool(
                    settings.rag_query_rewrite_enabled and self._rewriter
                ),
                "hybrid_enabled": bool(
                    settings.rag_hybrid_enabled and self._hybrid_retriever
                ),
                "rerank_enabled": rerank_active,
                "duration_rewrite_ms": round(dur_rewrite, 1),
                "duration_retrieval_ms": round(dur_retrieve, 1),
                "duration_rerank_ms": round(dur_rerank, 1),
                "duration_generation_ms": round(dur_generate, 1),
                "primary_query": prepared.english_query[:160],
                "alt_queries": len(prepared.alternative_queries),
                "keywords": len(prepared.keywords),
                "llm_model": getattr(get_chat_llm(), "model", None),
            },
        )

    @staticmethod
    def _to_citation(chunk: RetrievedChunk) -> SourceCitation:
        excerpt = chunk.content[:300] + ("..." if len(chunk.content) > 300 else "")
        return SourceCitation(
            source=chunk.source,
            filename=chunk.filename,
            chunk_index=chunk.chunk_index,
            excerpt=excerpt,
            score=chunk.score,
        )

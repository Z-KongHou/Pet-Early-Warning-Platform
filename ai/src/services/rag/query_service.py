"""RAG query orchestration: retrieve context and generate LLM answers."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import asdict, dataclass

from clients.llm import get_chat_llm
from config import settings
from services.rag.chat_history import ChatTurn, build_retrieval_query, truncate_history
from services.rag.language_detect import detect_language_code
from services.rag.prompt_builder import build_rag_prompt
from services.rag.query_translator import PreparedQuery, QueryTranslator
from services.rag.retriever import RagRetriever, RetrievedChunk

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
    translate_model: str | None = None


class QueryService:
    def __init__(
        self,
        retriever: RagRetriever,
        translator: QueryTranslator | None = None,
    ) -> None:
        self._retriever = retriever
        self._translator = translator

    def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        history: list[ChatTurn] | None = None,
    ) -> QueryResult:
        chat_history = self._normalize_history(history)
        prepared = self._prepare_query(question, chat_history)
        chunks = self._retriever.retrieve(prepared.english_query, top_k=top_k)
        if not chunks:
            raise ValueError("No relevant knowledge found; run POST /api/rag/ingest first")

        llm = get_chat_llm()
        prompt = build_rag_prompt(
            prepared.original,
            chunks,
            history=chat_history,
            reply_language=prepared.language,
        )
        logger.info(
            "RAG query: chunks=%d lang=%s history=%d english_query=%r llm=%s",
            len(chunks),
            prepared.language,
            len(chat_history),
            prepared.english_query,
            llm.model,
        )
        answer = llm.chat(prompt.system, prompt.user)

        return QueryResult(
            question=prepared.original,
            answer=answer,
            sources=[self._to_citation(chunk) for chunk in chunks],
            llm_model=llm.model,
            detected_language=prepared.language,
            english_question=prepared.english_query
            if prepared.english_query != prepared.original
            else None,
            translate_model=None,
        )

    def ask_stream(
        self,
        question: str,
        *,
        top_k: int | None = None,
        history: list[ChatTurn] | None = None,
    ) -> Iterator[tuple[str, dict]]:
        chat_history = self._normalize_history(history)
        prepared = self._prepare_query(question, chat_history)
        chunks = self._retriever.retrieve(prepared.english_query, top_k=top_k)
        if not chunks:
            yield "error", {"message": "No relevant knowledge found; run POST /api/rag/ingest first", "code": 40001}
            return

        llm = get_chat_llm()
        prompt = build_rag_prompt(
            prepared.original,
            chunks,
            history=chat_history,
            reply_language=prepared.language,
        )
        citations = [self._to_citation(chunk) for chunk in chunks]
        english_question = (
            prepared.english_query
            if prepared.english_query != prepared.original
            else None
        )

        logger.info(
            "RAG stream: chunks=%d lang=%s history=%d english_query=%r llm=%s",
            len(chunks),
            prepared.language,
            len(chat_history),
            prepared.english_query,
            llm.model,
        )

        yield "meta", {
            "question": prepared.original,
            "sources": [asdict(c) for c in citations],
            "llm_model": llm.model,
            "detected_language": prepared.language,
            "english_question": english_question,
        }

        parts: list[str] = []
        for delta in llm.stream_chat(prompt.system, prompt.user):
            parts.append(delta)
            yield "delta", {"text": delta}

        answer = "".join(parts)

        yield "done", {
            "question": prepared.original,
            "answer": answer,
            "sources": [asdict(c) for c in citations],
            "llm_model": llm.model,
            "detected_language": prepared.language,
            "english_question": english_question,
            "translate_model": None,
        }

    def _normalize_history(self, history: list[ChatTurn] | None) -> list[ChatTurn]:
        if not history:
            return []
        return truncate_history(history)

    def _prepare_query(self, question: str, history: list[ChatTurn]) -> PreparedQuery:
        text = question.strip()
        if not text:
            raise ValueError("Question must not be empty")

        retrieval_text = build_retrieval_query(text, history)

        if settings.rag_query_translation_enabled and self._translator is not None:
            prepared = self._translator.prepare(retrieval_text)
            return PreparedQuery(
                original=text,
                language=detect_language_code(text),
                english_query=prepared.english_query,
            )

        return PreparedQuery(
            original=text,
            language=detect_language_code(text),
            english_query=retrieval_text,
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

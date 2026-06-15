"""RAG knowledge retrieval tools for the Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.rag.retrieval.translator import PreparedQuery

if TYPE_CHECKING:
    from repositories.facts_repository import FactsRepository
    from repositories.preference_repository import PreferenceRepository
    from services.rag.retrieval.hybrid import HybridRetriever
    from services.rag.retrieval.rewriter import QueryRewriter
    from services.rag.retrieval.vector import RagRetriever
    from services.rag.retrieval.reranker import LlmReranker


class SearchKnowledgeBaseTool:
    """Search the veterinary knowledge base via hybrid retrieval (vector + BM25)."""

    name = "search_knowledge_base"
    description = (
        "Search the hamster veterinary knowledge base for information about diseases, "
        "symptoms, treatments, medications, care, and husbandry. Uses combined semantic "
        "and keyword search. Use this for most factual questions about hamster health."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query in English or Chinese. Be specific — include disease names, symptoms, or medications for best results.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (1-8)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        retriever: RagRetriever,
        hybrid_retriever: HybridRetriever | None = None,
        rewriter: QueryRewriter | None = None,
        reranker: LlmReranker | None = None,
    ) -> None:
        self._retriever = retriever
        self._hybrid = hybrid_retriever
        self._rewriter = rewriter
        self._reranker = reranker

    def execute(self, query: str, top_k: int = 5) -> str:
        query = query.strip()
        if not query:
            return "(no query provided)"

        top_k = max(1, min(top_k, 8))

        # Prefer hybrid retrieval when available
        if self._hybrid is not None:
            prepared = PreparedQuery(
                original=query,
                language="en",
                english_query=query,
                alternative_queries=[],
                keywords=[],
            )
            chunks = self._hybrid.retrieve(prepared, top_k=top_k)
        else:
            chunks = self._retriever.retrieve(query, top_k=top_k)

        # Rerank if available
        if self._reranker is not None and chunks:
            chunks = self._reranker.rerank(query, chunks, top_n=min(top_k, len(chunks)))

        if not chunks:
            return "No relevant information found in the knowledge base."

        lines: list[str] = [f"Found {len(chunks)} result(s):\n"]
        for i, chunk in enumerate(chunks, 1):
            src = chunk.filename or chunk.source or "unknown"
            excerpt = chunk.content[:400].replace("\n", " ").strip()
            lines.append(f"[{i}] {src} (score={chunk.score:.2f})\n   {excerpt}\n")

        return "\n".join(lines)


class LookupFactsTool:
    """Look up structured veterinary facts from the curated database."""

    name = "lookup_structured_facts"
    description = (
        "Look up structured veterinary facts (disease → symptoms → pathogen → drug → dosage) "
        "from a curated database. Use this for PRECISE questions about specific diseases, "
        "their symptoms, pathogens, recommended medications, and dosages. "
        "This is more accurate than search_knowledge_base for drug/dosage questions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "disease": {
                "type": "string",
                "description": "Disease name to search for (e.g. '湿尾症', 'wet tail')",
            },
            "symptom": {
                "type": "string",
                "description": "Symptom to search for (e.g. '腹泻', 'diarrhea')",
            },
            "drug": {
                "type": "string",
                "description": "Medication/drug name to search for (e.g. '四环素', 'tetracycline')",
            },
        },
    }

    def __init__(self, facts_repo: FactsRepository) -> None:
        self._repo = facts_repo

    def execute(self, disease: str = "", symptom: str = "", drug: str = "") -> str:
        if not any([disease, symptom, drug]):
            return "(no search criteria provided)"

        if disease or symptom or drug:
            facts = self._repo.search_exact(
                disease=disease.strip() if disease else "",
                symptom=symptom.strip() if symptom else "",
                drug=drug.strip() if drug else "",
                limit=5,
            )
        else:
            facts = []

        if not facts:
            # Fall back to fuzzy search
            query = disease or symptom or drug
            facts = self._repo.search(query.strip(), limit=5) if query else []

        if not facts:
            return "No matching facts found in the database."

        lines: list[str] = [f"Found {len(facts)} fact(s):\n"]
        for fact in facts:
            parts: list[str] = []
            if fact.get("disease"):
                parts.append(f"Disease: {fact['disease']}")
            if fact.get("symptom"):
                parts.append(f"Symptom: {fact['symptom']}")
            if fact.get("pathogen"):
                parts.append(f"Pathogen: {fact['pathogen']}")
            if fact.get("drug"):
                parts.append(f"Drug: {fact['drug']}")
            if fact.get("dosage"):
                parts.append(f"Dosage: {fact['dosage']}")
            source = fact.get("source_file", "")
            confidence = fact.get("confidence", 1.0)
            lines.append(f"- {' | '.join(parts)} (source: {source}, confidence: {confidence:.1f})")

        return "\n".join(lines)


class GetUserContextTool:
    """Retrieve stored user preferences and pet profiles."""

    name = "get_user_context"
    description = (
        "Retrieve stored information about the user's pets (name, species, age, sex, "
        "medical history) and user preferences (experience level, language style, concerns). "
        "ALWAYS call this first when the user mentions 'my hamster' or references their pet "
        "by name. Also call it when asking personalized questions."
    )
    parameters = {"type": "object", "properties": {}}

    def __init__(self, prefs_repo: PreferenceRepository) -> None:
        self._repo = prefs_repo

    def execute(self) -> str:
        text = self._repo.format_for_prompt()
        if not text:
            return "No user preferences or pet profiles stored yet. The user hasn't shared information about their pets. You can ask them about their pet (species, age, medical history) if relevant."
        return text

"""Register all agent tools into a ToolRegistry.

Tool philosophy: few, broad tools > many narrow tools.
The LLM performs better with 4 tools than 8.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clients.backend_client import BackendClient
from services.rag.agent.registry import ToolRegistry
from services.rag.agent.tools.database_context import ExecuteSqlTool
from services.rag.agent.tools.knowledge import (
    GetUserContextTool,
    LookupFactsTool,
    SearchKnowledgeBaseTool,
)

if TYPE_CHECKING:
    from repositories.facts_repository import FactsRepository
    from repositories.preference_repository import PreferenceRepository
    from services.rag.retrieval.hybrid import HybridRetriever
    from services.rag.retrieval.rewriter import QueryRewriter
    from services.rag.retrieval.vector import RagRetriever
    from services.rag.retrieval.reranker import LlmReranker


def register_default_tools(
    registry: ToolRegistry,
    *,
    retriever: RagRetriever,
    hybrid_retriever: HybridRetriever | None = None,
    rewriter: QueryRewriter | None = None,
    reranker: LlmReranker | None = None,
    facts_repo: FactsRepository | None = None,
    prefs_repo: PreferenceRepository | None = None,
    backend_client: BackendClient | None = None,
) -> ToolRegistry:
    """Register all available tools (4 total)."""

    # 1. SQL query tool — AI writes its own SELECT statements
    if backend_client is not None:
        registry.register(ExecuteSqlTool(backend_client=backend_client))

    # 2. Knowledge base search
    registry.register(
        SearchKnowledgeBaseTool(
            retriever=retriever,
            hybrid_retriever=hybrid_retriever,
            rewriter=rewriter,
            reranker=reranker,
        )
    )

    # 3. Curated veterinary facts
    if facts_repo is not None:
        registry.register(LookupFactsTool(facts_repo=facts_repo))

    # 4. LLM-extracted user preferences
    if prefs_repo is not None:
        registry.register(GetUserContextTool(prefs_repo=prefs_repo))

    return registry

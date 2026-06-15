"""Register all agent tools into a ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.rag.agent.registry import ToolRegistry
from services.rag.agent.tools.monitoring import CheckCurrentStateTool, GetActivityHistoryTool
from services.rag.agent.tools.knowledge import (
    GetUserContextTool,
    LookupFactsTool,
    SearchKnowledgeBaseTool,
)

if TYPE_CHECKING:
    from repositories.facts_repository import FactsRepository
    from repositories.frame_repository import SQLiteFrameRepository
    from repositories.preference_repository import PreferenceRepository
    from repositories.state_repository import MemoryStateRepository
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
    frame_repo: SQLiteFrameRepository | None = None,
    state_repo: MemoryStateRepository | None = None,
) -> ToolRegistry:
    """Register all available tools into the given registry.

    Each tool receives its dependencies via constructor injection.
    Tools with missing dependencies are skipped (with a warning).
    """

    # Knowledge retrieval tools
    registry.register(
        SearchKnowledgeBaseTool(
            retriever=retriever,
            hybrid_retriever=hybrid_retriever,
            rewriter=rewriter,
            reranker=reranker,
        )
    )

    if facts_repo is not None:
        registry.register(LookupFactsTool(facts_repo=facts_repo))

    if prefs_repo is not None:
        registry.register(GetUserContextTool(prefs_repo=prefs_repo))

    # Pet monitoring tools
    if frame_repo is not None:
        registry.register(GetActivityHistoryTool(frame_repo=frame_repo))

    if state_repo is not None:
        registry.register(CheckCurrentStateTool(state_repo=state_repo))

    return registry

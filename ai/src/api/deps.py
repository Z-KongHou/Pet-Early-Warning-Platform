from functools import lru_cache

from clients.embedding_client import get_embeddings
from clients.ezviz_client import EzvizClient
from clients.timestamp_extractor import TimestampExtractor
from config import settings
from repositories.bm25_index import Bm25IndexRepository
from repositories.facts_repository import FactsRepository
from repositories.frame_repository import SQLiteFrameRepository
from repositories.preference_repository import PreferenceRepository
from repositories.state_repository import MemoryStateRepository
from repositories.vector_store import VectorStoreRepository
from services.hamster.service import AnalyzeHamsterUseCase
from services.rag.extraction.facts import FactExtractor
from services.rag.orchestration.ingest import IngestService
from services.rag.orchestration.query import QueryService
from services.rag.extraction.preferences import PreferenceExtractor
from services.rag.retrieval.hybrid import HybridRetriever
from services.rag.retrieval.rewriter import QueryRewriter
from services.rag.retrieval.translator import QueryTranslator
from services.rag.retrieval.vector import RagRetriever
from services.rag.retrieval.reranker import LlmReranker
from services.rag.agent.registry import ToolRegistry
from services.rag.agent.loop import AgentLoop
from services.rag.agent.tools import register_default_tools
from clients.llm.client import get_chat_llm


@lru_cache
def get_state_repository() -> MemoryStateRepository:
    return MemoryStateRepository()


@lru_cache
def get_frame_repository() -> SQLiteFrameRepository:
    repo = SQLiteFrameRepository()
    repo.init_schema()
    return repo


@lru_cache
def get_timestamp_extractor() -> TimestampExtractor:
    return TimestampExtractor()


@lru_cache
def get_analyze_hamster_use_case() -> AnalyzeHamsterUseCase:
    return AnalyzeHamsterUseCase(
        ezviz=EzvizClient(),
        state_repository=get_state_repository(),
        frame_repository=get_frame_repository(),
        timestamp_extractor=get_timestamp_extractor(),
    )


def get_analyze_hamster_use_case_dep() -> AnalyzeHamsterUseCase:
    return get_analyze_hamster_use_case()


@lru_cache
def get_bm25_index() -> Bm25IndexRepository:
    return Bm25IndexRepository()


@lru_cache
def get_facts_repository() -> FactsRepository:
    return FactsRepository()


@lru_cache
def get_fact_extractor() -> FactExtractor:
    return FactExtractor()


@lru_cache
def get_preference_repository() -> PreferenceRepository:
    return PreferenceRepository()


@lru_cache
def get_preference_extractor() -> PreferenceExtractor:
    return PreferenceExtractor()


@lru_cache
def get_vector_store() -> VectorStoreRepository:
    return VectorStoreRepository(embeddings=get_embeddings())


@lru_cache
def get_ingest_service() -> IngestService:
    return IngestService(
        vector_store=get_vector_store(),
        bm25_index=get_bm25_index(),
        fact_extractor=get_fact_extractor(),
        facts_repo=get_facts_repository(),
    )


@lru_cache
def get_rag_retriever() -> RagRetriever:
    return RagRetriever(vector_store=get_vector_store())


@lru_cache
def get_hybrid_retriever() -> HybridRetriever:
    return HybridRetriever(
        vector_store=get_vector_store(),
        bm25_index=get_bm25_index(),
    )


@lru_cache
def get_reranker() -> LlmReranker:
    return LlmReranker()


@lru_cache
def get_query_translator() -> QueryTranslator:
    return QueryTranslator()


@lru_cache
def get_query_rewriter() -> QueryRewriter:
    return QueryRewriter()


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Build the agent tool registry with all available tools."""
    registry = ToolRegistry()
    register_default_tools(
        registry,
        retriever=get_rag_retriever(),
        hybrid_retriever=get_hybrid_retriever() if settings.rag_hybrid_enabled else None,
        rewriter=get_query_rewriter() if settings.rag_query_rewrite_enabled else None,
        reranker=get_reranker() if settings.rag_rerank_enabled else None,
        facts_repo=get_facts_repository(),
        prefs_repo=get_preference_repository(),
        frame_repo=get_frame_repository(),
        state_repo=get_state_repository(),
    )
    return registry


@lru_cache
def get_agent_loop() -> AgentLoop:
    """Create the LLM Agent loop (only used when RAG_AGENT_ENABLED=true)."""
    from clients.llm.client import OpenAICompatibleChatLlm
    llm = get_chat_llm()
    if not isinstance(llm, OpenAICompatibleChatLlm):
        raise RuntimeError("Agent mode requires OpenAICompatibleChatLlm (DeepSeek API)")
    return AgentLoop(
        registry=get_tool_registry(),
        llm=llm,
    )


@lru_cache
def get_query_service() -> QueryService:
    translator = get_query_translator() if settings.rag_query_translation_enabled else None
    # Rewriter injected separately; QueryService will read the flag itself to decide usage
    rewriter = get_query_rewriter() if settings.rag_query_rewrite_enabled else None
    hybrid = get_hybrid_retriever() if settings.rag_hybrid_enabled else None
    reranker = get_reranker() if settings.rag_rerank_enabled else None
    agent_loop = get_agent_loop() if settings.rag_agent_enabled else None
    return QueryService(
        retriever=get_rag_retriever(),
        translator=translator,
        rewriter=rewriter,
        hybrid_retriever=hybrid,
        reranker=reranker,
        facts_repo=get_facts_repository(),
        prefs_repo=get_preference_repository(),
        pref_extractor=get_preference_extractor(),
        agent_loop=agent_loop,
    )

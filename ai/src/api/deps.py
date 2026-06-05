from functools import lru_cache

from clients.embedding_client import get_embeddings
from clients.ezviz_client import EzvizClient
from clients.timestamp_extractor import TimestampExtractor
from config import settings
from repositories.frame_repository import SQLiteFrameRepository
from repositories.state_repository import MemoryStateRepository
from repositories.vector_store import VectorStoreRepository
from services.hamster.service import AnalyzeHamsterUseCase
from services.rag.ingest_service import IngestService
from services.rag.query_service import QueryService
from services.rag.query_translator import QueryTranslator
from services.rag.retriever import RagRetriever


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
def get_vector_store() -> VectorStoreRepository:
    return VectorStoreRepository(embeddings=get_embeddings())


@lru_cache
def get_ingest_service() -> IngestService:
    return IngestService(vector_store=get_vector_store())


@lru_cache
def get_rag_retriever() -> RagRetriever:
    return RagRetriever(vector_store=get_vector_store())


@lru_cache
def get_query_translator() -> QueryTranslator:
    return QueryTranslator()


@lru_cache
def get_query_service() -> QueryService:
    translator = get_query_translator() if settings.rag_query_translation_enabled else None
    return QueryService(retriever=get_rag_retriever(), translator=translator)

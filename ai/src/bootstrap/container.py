from functools import lru_cache

from application.analyze_hamster import AnalyzeHamsterUseCase
from infrastructure.external_services.ezviz_client import EzvizClient
from infrastructure.external_services.timestamp_extractor import TimestampExtractor
from infrastructure.persistence.memory_state_repository import MemoryStateRepository
from infrastructure.persistence.sqlite_frame_repository import SQLiteFrameRepository


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

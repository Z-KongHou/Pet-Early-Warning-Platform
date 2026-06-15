import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_LLM_MODEL_ALIASES = {
    "dsv4": "deepseek-v4-flash",
    "dsv4-flash": "deepseek-v4-flash",
    "dsv4-pro": "deepseek-v4-pro",
}


def _llm_model_name(raw: str) -> str:
    key = raw.strip().lower()
    return _LLM_MODEL_ALIASES.get(key, raw.strip())


def _env_first(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip():
            return value.strip()
    return default


def _normalize_llm_api_key(raw: str) -> str:
    key = raw.strip()
    if key.startswith("sk-sk-"):
        return "sk-" + key[6:]
    return key


def _normalize_llm_base_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    if url == "https://api.deepseek.com":
        return "https://api.deepseek.com/v1"
    if "api.deepseek.com" in url and not url.endswith("/v1"):
        return f"{url}/v1"
    return url


@dataclass(frozen=True)
class Settings:
    ezviz_access_token: str = os.getenv(
        "EZVIZ_ACCESS_TOKEN",
        "at.4uqsl8in7pc483xqao8ymm1z1vkpgu8p-64ehzsbtsb-01goxjp-luctlwd8i",
    )
    pet_detection_api: str = "https://open.ys7.com/api/service/intelligence/algo/analysis/pet_detection"
    max_request_size: int = 50 * 1024 * 1024
    max_image_kb_for_api: int = 500
    stationary_threshold: int = 60
    no_eating_threshold: int = 120
    movement_threshold: float = 0.05
    max_history: int = 10
    bowl_empty_blue_ratio: float = 0.85
    max_history_records: int = 3
    max_frames_per_camera: int = 500
    max_sample_frames: int = 20
    analysis_window_seconds: int = 3 * 60
    day_start_hour: int = 8
    day_end_hour: int = 22
    day_stationary_threshold: int = 3 * 60
    night_stationary_threshold: int = 3 * 60
    day_eating_threshold: int = 3 * 60
    night_eating_threshold: int = 3 * 60
    database_path: str = os.getenv("PET_ANALYSIS_DB_PATH", "pet_analysis.db")
    upload_dir_name: str = os.getenv("PET_UPLOAD_DIR", "upload")
    rag_data_dir: str = os.getenv("RAG_DATA_DIR", "data")
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "chroma_db")
    rag_chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "512"))
    rag_chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
    rag_chunk_min_chars: int = int(os.getenv("RAG_CHUNK_MIN_CHARS", "50"))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    ollama_translate_model: str = os.getenv("OLLAMA_TRANSLATE_MODEL", "qwen2.5:0.5b")
    ollama_translate_temperature: float = float(os.getenv("OLLAMA_TRANSLATE_TEMPERATURE", "0"))
    ollama_llm_model: str = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:0.5b")
    ollama_llm_temperature: float = float(os.getenv("OLLAMA_LLM_TEMPERATURE", "0.2"))
    rag_query_translation_enabled: bool = os.getenv("RAG_QUERY_TRANSLATION", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    chroma_collection_name: str = os.getenv("CHROMA_COLLECTION_NAME", "yingshi_rag")
    llm_api_key: str = _normalize_llm_api_key(_env_first("LLM_API_KEY", "DEEPSEEK_API_KEY"))
    llm_base_url: str = _normalize_llm_base_url(
        _env_first("LLM_BASE_URL", "DEEPSEEK_BASE_URL", default="https://api.deepseek.com/v1")
    )
    llm_model: str = _llm_model_name(
        _env_first("LLM_MODEL", "DEEPSEEK_MODEL", default="deepseek-v4-flash")
    )
    llm_temperature: float = float(
        _env_first("LLM_TEMPERATURE", "DEEPSEEK_TEMPERATURE", default="0.2")
    )
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "12"))
    rag_max_distance: float = float(os.getenv("RAG_MAX_DISTANCE", "1.5"))
    rag_chat_max_turns: int = int(os.getenv("RAG_CHAT_MAX_TURNS", "6"))
    rag_chat_max_history_tokens: int = int(os.getenv("RAG_CHAT_MAX_HISTORY_TOKENS", "2000"))

    # Day 1+ Hybrid RAG feature flags (default off for safe rollout)
    rag_query_rewrite_enabled: bool = os.getenv("RAG_QUERY_REWRITE_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    rag_query_rewrite_max_queries: int = int(os.getenv("RAG_QUERY_REWRITE_MAX_QUERIES", "3"))

    # Day 2 Hybrid RAG: BM25 + RRF (default off for safe rollout)
    rag_hybrid_enabled: bool = os.getenv("RAG_HYBRID_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    rag_vector_top_n: int = int(os.getenv("RAG_VECTOR_TOP_N", "20"))
    rag_bm25_top_n: int = int(os.getenv("RAG_BM25_TOP_N", "20"))
    rag_rrf_k: int = int(os.getenv("RAG_RRF_K", "60"))

    # Day 3 Rerank (LLM-based as default; cross-encoder when torch/sentence-transformers available)
    rag_rerank_enabled: bool = os.getenv("RAG_RERANK_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    rag_rerank_backend: str = os.getenv("RAG_RERANK_BACKEND", "llm")  # "llm" or "cross_encoder"
    rag_rerank_top_n: int = int(os.getenv("RAG_RERANK_TOP_N", "5"))
    rag_rerank_candidate_n: int = int(os.getenv("RAG_RERANK_CANDIDATE_N", "20"))

    # Agent mode: LLM-driven tool-calling instead of fixed RAG pipeline
    rag_agent_enabled: bool = os.getenv("RAG_AGENT_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def upload_dir(self) -> Path:
        return self.base_dir / self.upload_dir_name

    @property
    def rag_data_path(self) -> Path:
        return self.base_dir / self.rag_data_dir

    @property
    def chroma_path(self) -> Path:
        return self.base_dir / self.chroma_persist_dir


settings = Settings()

"""Health check with backend status for all RAG components."""

import logging

import requests
from fastapi import APIRouter, Depends

from api.deps import get_bm25_index, get_facts_repository, get_preference_repository, get_vector_store
from config import settings
from repositories.bm25_index import Bm25IndexRepository
from repositories.facts_repository import FactsRepository
from repositories.preference_repository import PreferenceRepository
from repositories.vector_store import VectorStoreRepository
from utils.response import success_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    vector_store: VectorStoreRepository = Depends(get_vector_store),
    bm25_index: Bm25IndexRepository = Depends(get_bm25_index),
    facts_repo: FactsRepository = Depends(get_facts_repository),
    prefs_repo: PreferenceRepository = Depends(get_preference_repository),
):
    backends: dict[str, dict] = {}

    # Chroma
    try:
        vs_count = vector_store.count()
        backends["chroma"] = {"ok": True, "chunks": vs_count}
    except Exception as exc:
        backends["chroma"] = {"ok": False, "error": str(exc)[:120]}

    # BM25
    try:
        bm25_count = bm25_index.count
        backends["bm25"] = {"ok": True, "chunks": bm25_count}
    except Exception as exc:
        backends["bm25"] = {"ok": False, "error": str(exc)[:120]}

    # Ollama
    try:
        resp = requests.get(
            f"{settings.ollama_base_url}/api/tags",
            timeout=3,
        )
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            backends["ollama"] = {"ok": True, "models": models}
        else:
            backends["ollama"] = {"ok": False, "status": resp.status_code}
    except Exception as exc:
        backends["ollama"] = {"ok": False, "error": str(exc)[:120]}

    # DeepSeek LLM
    try:
        resp = requests.get(
            settings.llm_base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=5,
        )
        backends["deepseek"] = {"ok": resp.status_code == 200, "status": resp.status_code}
    except Exception as exc:
        backends["deepseek"] = {"ok": False, "error": str(exc)[:120]}

    # Structured facts (SQLite)
    try:
        facts_count = facts_repo.count
        backends["facts"] = {"ok": True, "rows": facts_count}
    except Exception as exc:
        backends["facts"] = {"ok": False, "error": str(exc)[:120]}

    # User preferences & pet profiles (SQLite)
    try:
        pets = prefs_repo.get_pets()
        prefs = prefs_repo.get_all_prefs()
        backends["preferences"] = {"ok": True, "pets": len(pets), "prefs": len(prefs)}
    except Exception as exc:
        backends["preferences"] = {"ok": False, "error": str(exc)[:120]}

    all_ok = all(v.get("ok", False) for v in backends.values())
    overall = "ok" if all_ok else "degraded"

    logger.info("Health check: overall=%s backends=%s", overall, {k: v.get("ok") for k, v in backends.items()})

    return success_response({
        "status": overall,
        "backends": backends,
    })

"""Ollama ?? Embedding?nomic-embed-text?? Nomic ??????"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings

from config import settings

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class NomicOllamaEmbeddings(Embeddings):
    """? nomic-embed-text ????????? document/query ???"""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._inner = OllamaEmbeddings(
            model=model or settings.ollama_embed_model,
            base_url=base_url or settings.ollama_base_url,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"{DOCUMENT_PREFIX}{text}" for text in texts]
        return self._inner.embed_documents(prefixed)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(f"{QUERY_PREFIX}{text}")


def get_embeddings() -> Embeddings:
    return NomicOllamaEmbeddings()

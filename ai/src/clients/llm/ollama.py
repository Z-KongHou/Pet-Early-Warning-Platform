"""Ollama ???????"""

from __future__ import annotations

from langchain_ollama import ChatOllama

from clients.llm._langchain_chat import invoke_chat
from clients.llm.types import ChatLlmProvider
from config import settings


class OllamaLlmProvider:
    provider_id = "ollama"

    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        self._model = model or settings.ollama_llm_model
        self._temperature = (
            temperature if temperature is not None else settings.ollama_llm_temperature
        )

    @property
    def model(self) -> str:
        return self._model

    def chat(self, system: str, user: str) -> str:
        llm = ChatOllama(
            model=self._model,
            base_url=settings.ollama_base_url,
            temperature=self._temperature,
        )
        return invoke_chat(llm, system, user)


def build_ollama(
    model: str | None = None,
    temperature: float | None = None,
) -> ChatLlmProvider:
    return OllamaLlmProvider(model=model, temperature=temperature)

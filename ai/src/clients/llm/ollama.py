"""Ollama ???????"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from clients.llm.base import ChatLlm
from config import settings


class OllamaLlmProvider:
    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        self._model = model or settings.ollama_llm_model
        self._temperature = (
            temperature if temperature is not None else settings.ollama_llm_temperature
        )

    @property
    def provider(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def chat(self, system: str, user: str) -> str:
        llm = ChatOllama(
            model=self._model,
            base_url=settings.ollama_base_url,
            temperature=self._temperature,
        )
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        content = response.content
        return content.strip() if isinstance(content, str) else str(content).strip()

    def stream_chat(self, system: str, user: str):
        raise NotImplementedError("Ollama streaming not implemented yet")


def build_ollama(
    model: str | None = None,
    temperature: float | None = None,
) -> ChatLlm:
    return OllamaLlmProvider(model=model, temperature=temperature)

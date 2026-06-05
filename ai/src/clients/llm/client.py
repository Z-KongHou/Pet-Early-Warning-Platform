"""OpenAI Chat Completions ?? LLM?DeepSeek V4??? GLM ??????????"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from clients.llm.base import ChatLlm
from config import settings


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


def _extract_stream_delta(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


class OpenAICompatibleChatLlm:
    """? LLM_API_KEY / LLM_BASE_URL / LLM_MODEL ?????????? .env?"""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._temperature = temperature

    @property
    def provider(self) -> str:
        return "openai_compatible"

    @property
    def model(self) -> str:
        return self._model

    def chat(self, system: str, user: str) -> str:
        if not self._api_key:
            raise ValueError("??? LLM_API_KEY????? DEEPSEEK_API_KEY?")
        llm = ChatOpenAI(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=self._temperature,
        )
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return _extract_text(response.content)

    def stream_chat(self, system: str, user: str) -> Iterator[str]:
        if not self._api_key:
            raise ValueError("??? LLM_API_KEY????? DEEPSEEK_API_KEY?")
        llm = ChatOpenAI(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=self._temperature,
        )
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        for chunk in llm.stream(messages):
            delta = _extract_stream_delta(chunk.content)
            if delta:
                yield delta


def clear_chat_llm_cache() -> None:
    get_chat_llm.cache_clear()


@lru_cache
def get_chat_llm() -> ChatLlm:
    return OpenAICompatibleChatLlm(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
    )

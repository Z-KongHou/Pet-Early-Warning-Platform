"""OpenAI Chat Completions 兼容 LLM（DeepSeek V4、GLM 等通用接口）"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
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
            raise ValueError("请设置 LLM_API_KEY（或 DEEPSEEK_API_KEY）")
        llm = self.build_chat_model()
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return _extract_text(response.content)

    def stream_chat(self, system: str, user: str) -> Iterator[str]:
        if not self._api_key:
            raise ValueError("请设置 LLM_API_KEY（或 DEEPSEEK_API_KEY）")
        llm = self.build_chat_model()
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        for chunk in llm.stream(messages):
            delta = _extract_stream_delta(chunk.content)
            if delta:
                yield delta

    # ── Tool Calling (Agent 模式) ────────────────────────────────

    def build_chat_model(self) -> ChatOpenAI:
        """Create a ChatOpenAI instance with current config."""
        return ChatOpenAI(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=self._temperature,
        )

    def chat_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[dict],
    ) -> AIMessage:
        """Chat with tool calling support (OpenAI function-calling format).

        Args:
            messages: LangChain BaseMessage list (SystemMessage, HumanMessage,
                      AIMessage, ToolMessage, etc.)
            tools: OpenAI-compatible tool definitions list.
                   Each tool: {\"type\": \"function\", \"function\": {\"name\":..., \"description\":..., \"parameters\":...}}

        Returns:
            AIMessage — may have .tool_calls populated if the model decides to
            call tools, or .content set to the final answer text.
        """
        if not self._api_key:
            raise ValueError("请设置 LLM_API_KEY（或 DEEPSEEK_API_KEY）")
        llm = self.build_chat_model()
        model = llm.bind_tools(tools)
        return model.invoke(messages)

    def stream_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[dict],
    ) -> Iterator[AIMessage]:
        """Stream with tool calling support.

        Yields AIMessage chunks. The caller should accumulate
        tool_call_chunks and content for the final result.
        """
        if not self._api_key:
            raise ValueError("请设置 LLM_API_KEY（或 DEEPSEEK_API_KEY）")
        llm = self.build_chat_model()
        model = llm.bind_tools(tools)
        return model.stream(messages)


@lru_cache
def get_chat_llm() -> ChatLlm:
    return OpenAICompatibleChatLlm(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
    )

"""Chat LLM protocol for RAG generation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class ChatLlm(Protocol):
    @property
    def provider(self) -> str:
        ...

    @property
    def model(self) -> str:
        ...

    def chat(self, system: str, user: str) -> str:
        ...

    def stream_chat(self, system: str, user: str) -> Iterator[str]:
        ...


@dataclass(frozen=True)
class LlmProviderInfo:
    id: str
    label: str
    default_model: str
    requires_api_key: bool
    description: str

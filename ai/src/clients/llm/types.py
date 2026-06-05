"""LLM provider types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class ChatLlmProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    @property
    def model(self) -> str:
        ...

    def chat(self, system: str, user: str) -> str:
        ...


@dataclass(frozen=True)
class LlmProviderInfo:
    id: str
    name: str
    default_model: str
    requires_api_key: bool
    description: str

"""Chat LLM protocol for RAG generation."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


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

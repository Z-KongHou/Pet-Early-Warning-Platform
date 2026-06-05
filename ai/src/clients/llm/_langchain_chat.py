"""LangChain chat model invoke helper."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


def invoke_chat(llm: BaseChatModel, system: str, user: str) -> str:
    response = llm.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=user),
        ]
    )
    content = response.content
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()

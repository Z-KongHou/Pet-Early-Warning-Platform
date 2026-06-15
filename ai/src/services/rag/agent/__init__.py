"""LLM Agent with tool-calling for RAG and pet monitoring."""

from services.rag.agent.loop import AgentLoop
from services.rag.agent.registry import RagTool, ToolRegistry
from services.rag.agent.tools import register_default_tools

__all__ = ["AgentLoop", "RagTool", "ToolRegistry", "register_default_tools"]

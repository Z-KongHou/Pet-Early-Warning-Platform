"""Tool Protocol and Registry for the LLM Agent."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class RagTool(Protocol):
    """A tool that the Agent can call during its reasoning loop.

    Each tool has a name, description, and JSON Schema parameters
    that get sent to the LLM as function definitions (OpenAI format).
    """

    @property
    def name(self) -> str:
        """Unique tool identifier, e.g. 'search_knowledge_base'."""
        ...

    @property
    def description(self) -> str:
        """Natural-language description for the LLM to decide when to use."""
        ...

    @property
    def parameters(self) -> dict:
        """JSON Schema describing the tool's input parameters.

        Example:
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "search query"},
                "top_k": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
        """
        ...

    def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return a string observation for the Agent.

        The return value becomes the content of a ToolMessage so the
        LLM can read it on the next turn.
        """
        ...


class ToolRegistry:
    """Registry of all available tools for the Agent."""

    def __init__(self) -> None:
        self._tools: dict[str, RagTool] = {}

    def register(self, tool: RagTool) -> None:
        """Register a tool. Overwrites if name already exists."""
        self._tools[tool.name] = tool
        logger.info("ToolRegistry: registered tool %r", tool.name)

    def get(self, name: str) -> RagTool:
        """Get a tool by name. Raises KeyError if not found."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return tool

    def list_definitions(self) -> list[dict]:
        """Return tool definitions in OpenAI function-calling format.

        Used with ChatOpenAI.bind_tools().
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, **kwargs: Any) -> str:
        """Execute a tool by name and return the observation string."""
        tool = self.get(name)
        try:
            return tool.execute(**kwargs)
        except Exception as exc:
            logger.warning("Tool %r failed: %s", name, exc)
            return f"[Tool {name} returned an error: {exc}]"

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

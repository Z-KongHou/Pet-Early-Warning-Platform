"""ReAct Agent loop: LLM-driven tool calling for multi-skill Q&A.

The AgentLoop is the primary query path: an LLM that autonomously
decides which tools to call, in what order, and when to synthesize
a final answer. The fixed pipeline serves as fallback.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from clients.llm.client import OpenAICompatibleChatLlm
from services.rag.agent.registry import ToolRegistry
from services.rag.utils.history import ChatTurn
from services.rag.utils.language import detect_language_code

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5  # hard cap to prevent infinite loops

_SYSTEM_PROMPT = """You are a veterinary knowledge assistant for small pets (hamsters, mice, gerbils, etc.).

You have access to TOOLS that you can call to gather information. Think step by step:

1. For most questions about hamster diseases, symptoms, treatments, or care → call search_knowledge_base
2. For precise drug/dosage questions → call lookup_structured_facts
3. When the user mentions "my pet", "my hamster", or a pet name → call get_user_context FIRST, then search for relevant info
4. When the user asks about their pet's recent behavior or activity → call get_activity_history or check_current_state

You may call multiple tools. For example: get_user_context, then search_knowledge_base with a context-aware query.

RULES:
- If a tool returns no results, tell the user clearly. Suggest consulting a licensed veterinarian when appropriate.
- Reply in the SAME LANGUAGE as the user's question.
- Be concise, practical, helpful. Structure answers with: 1) key conclusion, 2) supporting details, 3) practical recommendations, 4) when to see a vet.
- Do NOT make up facts. Only use information from the tools.
- Do NOT call the same tool with the same arguments more than once.
"""


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result_summary: str
    duration_ms: float


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    detected_language: str = "en"
    iterations: int = 0


class AgentLoop:
    """LLM Agent that uses tool calling to answer multi-skill questions."""

    def __init__(
        self,
        registry: ToolRegistry,
        llm: OpenAICompatibleChatLlm,
        *,
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        self._registry = registry
        self._llm = llm
        self._max_iterations = max_iterations

    def run(
        self,
        question: str,
        history: list[ChatTurn] | None = None,
    ) -> AgentResult:
        """Run the agent loop and return the final answer.

        Args:
            question: User's current question.
            history: Previous conversation turns (oldest first).

        Returns:
            AgentResult with answer, tool call trace, and metadata.
        """
        lang = detect_language_code(question)
        tools = self._registry.list_definitions()

        # Build initial messages
        messages = self._build_initial_messages(question, history or [])

        tool_records: list[ToolCallRecord] = []
        iterations = 0

        for iteration in range(1, self._max_iterations + 1):
            iterations = iteration
            t0 = time.perf_counter()

            response = self._llm.chat_with_tools(messages, tools)
            messages.append(response)

            if not response.tool_calls:
                # No tool calls → final answer
                dur = (time.perf_counter() - t0) * 1000
                logger.info(
                    "Agent finished at iteration %d (%.0fms). %d tool calls total.",
                    iteration, dur, len(tool_records),
                )
                break

            # Execute tool calls
            for tc in response.tool_calls:
                name = tc.get("name", "unknown")
                args = tc.get("args", {})
                tc_id = tc.get("id", "")

                t_tool = time.perf_counter()
                observation = self._registry.execute(name, **args)
                dur_tool = (time.perf_counter() - t_tool) * 1000

                logger.info("Agent tool call: %s(%s) → %d chars (%.0fms)", name, args, len(observation), dur_tool)

                tool_records.append(ToolCallRecord(
                    name=name,
                    args=args,
                    result_summary=observation[:200] + ("..." if len(observation) > 200 else ""),
                    duration_ms=dur_tool,
                ))

                messages.append(ToolMessage(content=observation, tool_call_id=tc_id))
        else:
            # Exceeded max iterations — force final answer
            logger.warning("Agent hit max iterations (%d). Forcing final answer.", self._max_iterations)
            messages.append(HumanMessage(
                content="You've reached the maximum number of tool calls. "
                "Please synthesize a final answer based on the information gathered so far. "
                "If you don't have enough information, say so clearly."
            ))
            final_response = self._llm.chat_with_tools(messages, tools)
            messages.append(final_response)
            response = final_response

        answer = (response.content or "").strip() if hasattr(response, "content") else ""
        if not answer and isinstance(response, AIMessage):
            answer = str(response.content or "").strip()

        return AgentResult(
            answer=answer,
            tool_calls=tool_records,
            detected_language=lang,
            iterations=iterations,
        )

    def _build_initial_messages(
        self,
        question: str,
        history: list[ChatTurn],
    ) -> list:
        """Build the initial message list for the agent.

        Structure: [SystemMessage, ...history turns..., HumanMessage(question)]
        """
        # Tool descriptions for the system prompt
        tool_list = "\n".join(
            f"  - {t['function']['name']}: {t['function']['description']}"
            for t in self._registry.list_definitions()
        )

        system = SystemMessage(content=(
            _SYSTEM_PROMPT
            + f"\n\nAVAILABLE TOOLS:\n{tool_list}\n"
            + "\nRemember: reply in the same language as the user."
        ))

        messages: list = [system]

        # Convert ChatTurn history to LangChain messages
        for turn in history:
            content = turn.content.strip()
            if not content:
                continue
            if turn.role == "user":
                messages.append(HumanMessage(content=content))
            elif turn.role == "assistant":
                messages.append(AIMessage(content=content))

        # Current question
        messages.append(HumanMessage(content=question.strip()))

        return messages

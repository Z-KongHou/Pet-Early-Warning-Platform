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

You have 4 TOOLS. Use them wisely:
  - execute_sql → Run SELECT queries against the database. ALWAYS call this FIRST
    to get real user data (pet names, breeds, activity scores, alerts, etc).
  - search_knowledge_base → For diseases, symptoms, treatments, care guides.
  - lookup_structured_facts → For precise drug dosages, medical facts.
  - get_user_context → Supplementary: LLM-extracted pet profiles from past chats.

DATABASE SCHEMA (queries are auto-scoped — no need to write user_id column):

  hamsters(id, name, breed, birth_date, gender, weight, health_status, remark, created_at)
    gender: 0=unknown 1=male 2=female  |  health_status: 0=healthy 1=attention 2=critical

  cameras(id, hamster_id, name, device_key, channel_no, online_status, recording_enabled, last_online_time)
    online_status: 0=offline 1=online

  activity_history(id, hamster_id, camera_id, activity_score, status, analysis_result, created_at)
    status: normal/low/high.  Low=below-normal, high=critical danger.

  alerts(id, hamster_id, activity_status, activity_score, threshold, image_url, status, handler_id, handle_remark, created_at, handled_at)
    status: 0=pending 1=read 2=handled.  activity_status: normal/low/high.

  messages(id, hamster_id, alert_id, title, content, is_read, created_at)
    is_read: 0=unread 1=read

  pet_analysis(id, camera_id, timestamp, has_pet, movement_state, food_state, position_x, position_y, confidence)
    has_pet: 0=not-seen 1=seen.  movement_state: stationary/moving.

  pet_state(id, camera_id, last_eating_time, stationary_start_time, total_analyses,
            last_position_x, last_position_y, food_bowl_position_x, food_bowl_position_y)
  settings(id, key_name, key_value)

EXAMPLE QUERIES:
  - "What pets do I have?" → SELECT name, breed, weight, health_status FROM hamsters
  - "Any recent alerts?" → SELECT * FROM alerts ORDER BY created_at DESC LIMIT 10
  - "How active is my hamster?" → SELECT * FROM activity_history WHERE hamster_id = 1 ORDER BY created_at DESC LIMIT 5
  - "Unread messages?" → SELECT title, content FROM messages WHERE is_read = 0
  - "Camera status?" → SELECT name, online_status FROM cameras
  - "Recent detections?" → SELECT timestamp, has_pet, movement_state, food_state FROM pet_analysis WHERE camera_id = '3' ORDER BY timestamp DESC LIMIT 5

RULES:
- Always call execute_sql before mentioning any pet name or user data.
- Write clean SQL. The backend handles user scoping automatically.
- If the query returns 0 rows or fails, tell the user. Suggest a vet when appropriate.
- Reply in the SAME LANGUAGE as the user.
- Structure answers: 1) key finding, 2) details, 3) recommendations, 4) when to see a vet.
- Do NOT invent data. Do NOT call the same tool twice identically.
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

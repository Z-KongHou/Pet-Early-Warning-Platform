"""LLM-based user preference and pet profile extraction from conversations.

Runs after each RAG query completes (best-effort, non-blocking).
Updates the PreferenceRepository with extracted info.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """Extract the user's pet ownership info and preferences from this conversation.
Output ONLY a JSON object. No other text.

Conversation:
{conversation_text}

Output format:
{{
  "preferences": {{
    "experience_level": "beginner/intermediate/expert or null",
    "language_style": "preferred language style or null",
    "concerns": "topics the user is particularly concerned about or null"
  }},
  "pets": [
    {{
      "name": "pet name or null",
      "species": "叙利亚仓鼠/一线仓鼠/三线仓鼠/熊仔仓鼠/unknown",
      "age_months": number or null,
      "sex": "male/female/unknown",
      "notes": "medical history, special conditions etc."
    }}
  ]
}}

Rules:
- Only extract info explicitly stated. Leave unknown fields as null.
- If the user mentions "my hamster 豆豆 is 1 year old", extract name="豆豆", species="叙利亚仓鼠", age_months=12.
- Merge new info with existing; don't overwrite unless the user provides new info.
- If nothing new is found, output empty preferences and empty pets array.
"""


class PreferenceExtractor:
    """Extract user preferences and pet profiles from chat history using LLM."""

    def __init__(self, llm=None) -> None:
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            from clients.llm import get_chat_llm
            self._llm = get_chat_llm()
        return self._llm

    def extract(
        self,
        conversation_text: str,
        existing_pets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Extract prefs + pets from recent conversation.

        Returns dict with keys: 'preferences', 'pets'
        """
        prompt = _EXTRACT_PROMPT.format(conversation_text=conversation_text)
        if existing_pets:
            existing_json = json.dumps({"existing_pets": existing_pets}, ensure_ascii=False, indent=2)
            prompt += f"\n\nExisting pet profiles (update/merge, don't overwrite unless new info conflicts):\n{existing_json}"

        try:
            raw = self.llm.chat(
                "You are a precise JSON extractor. Output only valid JSON, no markdown, no explanation.",
                prompt,
            )
            return self._parse_result(raw)
        except Exception as exc:
            logger.warning("PreferenceExtractor failed: %s", exc)
            return {"preferences": {}, "pets": []}

    @staticmethod
    def _parse_result(raw: str) -> dict[str, Any]:
        from utils.parsing import parse_json_object
        return parse_json_object(raw, default={"preferences": {}, "pets": []})

"""Post-generation answer validation: citation integrity check.

Day 3 per hybrid-rag-3day-plan.md.
Detects hallucinated citation numbers (e.g., [7] when only 5 sources exist)
and logs warnings for observability.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass
class AnswerValidation:
    valid: bool
    illegal_refs: list[int] = field(default_factory=list)
    missing_refs: list[int] = field(default_factory=list)


class AnswerValidator:
    """Lightweight validation of LLM answers against provided sources."""

    def validate(self, answer: str, num_sources: int) -> AnswerValidation:
        """Check answer citations against the number of available sources.

        Returns an AnswerValidation with findings.
        Does NOT raise — always logs warnings for ops visibility.
        """
        if not answer:
            return AnswerValidation(valid=True)

        cited = {int(m) for m in _CITATION_RE.findall(answer)}
        valid_max = num_sources

        illegal = sorted([c for c in cited if c < 1 or c > valid_max])
        if illegal:
            logger.warning(
                "answer_validator: %d illegal citation(s) %s (max valid=%d) | answer[:200]=%r",
                len(illegal),
                illegal,
                valid_max,
                answer[:200],
            )

        # Check which valid source indices were never referenced (informational)
        all_valid = set(range(1, valid_max + 1))
        missing = sorted(all_valid - cited) if num_sources > 0 else []

        return AnswerValidation(
            valid=len(illegal) == 0,
            illegal_refs=illegal,
            missing_refs=missing,
        )

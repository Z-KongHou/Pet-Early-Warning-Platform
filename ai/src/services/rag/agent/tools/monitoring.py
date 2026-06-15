"""Pet monitoring tools for the Agent — query hamster activity data."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repositories.frame_repository import SQLiteFrameRepository
    from repositories.state_repository import MemoryStateRepository


class GetActivityHistoryTool:
    """Retrieve hamster activity history from the monitoring database."""

    name = "get_activity_history"
    description = (
        "Retrieve the hamster's recent activity history — movement, eating behavior, "
        "food bowl status, and any detected anomalies. Use this when the user asks about "
        "their pet's recent behavior patterns, activity level, or food intake."
    )
    parameters = {
        "type": "object",
        "properties": {
            "camera_id": {
                "type": "string",
                "description": "Camera identifier",
                "default": "default_camera",
            },
        },
    }

    def __init__(self, frame_repo: SQLiteFrameRepository) -> None:
        self._repo = frame_repo

    def execute(self, camera_id: str = "default_camera") -> str:
        try:
            history = self._repo.get_all_history(camera_id)
        except Exception as exc:
            return f"Failed to retrieve activity history: {exc}"

        if not history:
            return (
                "No activity history found for this camera. The hamster monitoring "
                "system hasn't recorded any analysis data yet. Ask the user to upload "
                "images for analysis via the hamster monitoring feature."
            )

        # Show the 5 most recent records
        recent = history[-5:]
        lines: list[str] = [f"Recent activity history ({len(history)} total records, showing last {len(recent)}):\n"]

        for i, record in enumerate(reversed(recent), 1):
            ts = record.get("timestamp", "unknown")
            has_pet = record.get("has_pet", False)
            is_moving = record.get("movement_state", False)
            food_state = record.get("food_state", "unknown")
            confidence = record.get("confidence", 0)

            status = "present" if has_pet else "absent"
            move = "moving" if is_moving else "stationary"
            lines.append(
                f"  [{i}] time={ts} | pet: {status}, {move}, food={food_state} (confidence={confidence:.2f})"
            )

        # Summarize trends
        pet_count = sum(1 for r in recent if r.get("has_pet"))
        moving_count = sum(1 for r in recent if r.get("movement_state"))
        lines.append(f"\nSummary (last {len(recent)} records):")
        lines.append(f"  Pet detected: {pet_count}/{len(recent)}")
        lines.append(f"  Active/moving: {moving_count}/{pet_count}" if pet_count > 0 else "  Active/moving: N/A")

        return "\n".join(lines)


class CheckCurrentStateTool:
    """Check the current running state of the hamster (in-memory state)."""

    name = "check_current_state"
    description = (
        "Check the hamster's current in-memory state — last known position, "
        "how long it's been stationary, when it last ate, and whether any anomalies "
        "(prolonged inactivity, not eating) are detected. Use this when the user "
        "asks 'how is my hamster now' or 'is my hamster OK right now'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "camera_id": {
                "type": "string",
                "description": "Camera identifier",
                "default": "default_camera",
            },
        },
    }

    def __init__(self, state_repo: MemoryStateRepository) -> None:
        self._state = state_repo

    def execute(self, camera_id: str = "default_camera") -> str:
        import time

        try:
            state = self._state.get(camera_id)
        except Exception as exc:
            return f"Failed to retrieve current state: {exc}"

        if state.get("total_analyses", 0) == 0:
            return (
                "No analysis has been performed yet for this camera. "
                "The hamster monitoring system hasn't recorded any data. "
                "Ask the user to upload images for analysis."
            )

        now = time.time()
        lines: list[str] = ["Current hamster state:\n"]

        # Position
        pos = state.get("last_position")
        if pos:
            lines.append(f"  Last known position: ({pos.get('x', '?')}, {pos.get('y', '?')})")

        # Stationary duration
        stationary_start = state.get("stationary_start_time", 0)
        if stationary_start:
            stationary_min = int((now - stationary_start) / 60)
            lines.append(f"  Stationary for: ~{stationary_min} minutes")

        # Last eating
        last_eating = state.get("last_eating_time", 0)
        if last_eating:
            eating_min = int((now - last_eating) / 60)
            lines.append(f"  Last eating: ~{eating_min} minutes ago")

        # Stats
        total = state.get("total_analyses", 0)
        lines.append(f"  Total analyses run: {total}")

        # History summary
        history = state.get("history", [])
        if history:
            recent = history[-3:]
            lines.append(f"\n  Recent activity (last {len(recent)} of {len(history)} records):")
            for h in reversed(recent):
                ts = h.get("timestamp", "?")
                moving = "moving" if h.get("is_moving") else "still"
                eating = "eating" if h.get("is_eating") else "not eating"
                food = h.get("food_status", "?")
                lines.append(f"    {ts}: {moving}, {eating}, food={food}")

        return "\n".join(lines)

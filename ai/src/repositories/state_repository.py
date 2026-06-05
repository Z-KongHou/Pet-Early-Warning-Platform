import time
from typing import Any


def _empty_state(now: float) -> dict[str, Any]:
    return {
        "last_position": None,
        "last_eating_time": now,
        "stationary_start_time": now,
        "food_bowl_position": None,
        "history": [],
        "total_analyses": 0,
    }


class MemoryStateRepository:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, camera_id: str) -> dict[str, Any]:
        if camera_id not in self._cache:
            self._cache[camera_id] = _empty_state(time.time())
        return self._cache[camera_id]

    def set_bowl_position(self, camera_id: str, bowl: dict[str, int]) -> None:
        state = self.get(camera_id)
        state["food_bowl_position"] = bowl

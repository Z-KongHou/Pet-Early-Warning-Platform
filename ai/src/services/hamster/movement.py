import time
from typing import Any

from config import settings


def movement_rate(prev_pos: dict, curr_pos: dict) -> float:
    prev_center = (prev_pos["x"] + prev_pos["width"] / 2, prev_pos["y"] + prev_pos["height"] / 2)
    curr_center = (curr_pos["x"] + curr_pos["width"] / 2, curr_pos["y"] + curr_pos["height"] / 2)
    distance = ((prev_center[0] - curr_center[0]) ** 2 + (prev_center[1] - curr_center[1]) ** 2) ** 0.5
    avg_size = ((prev_pos["width"] + prev_pos["height"]) + (curr_pos["width"] + curr_pos["height"])) / 4
    if avg_size <= 0:
        return 0.0
    return distance / avg_size


def is_moving_by_rate(rate: float) -> bool:
    return rate > settings.movement_threshold


def compare_with_history(history: list[dict], curr_pos: dict) -> list[dict[str, Any]]:
    movements = []
    for i, record in enumerate(reversed(history)):
        if not record.get("has_pet") or not record.get("position"):
            continue
        prev_pos = record["position"]
        rate = movement_rate(prev_pos, curr_pos)
        movements.append(
            {
                "from_image": f"history_{len(history) - i}",
                "to_image": "current",
                "movement_rate": round(rate, 4),
                "is_moving": is_moving_by_rate(rate),
                "time_diff": time.time() - record["timestamp"],
            }
        )
    return movements

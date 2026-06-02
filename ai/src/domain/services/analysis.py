import time

from domain.repositories import StateRepository
from domain.services.bowl import is_in_food_bowl
from domain.services.movement import is_moving_by_rate, movement_rate
from shared.config import settings


def update_pet_state(camera_id: str, analysis: dict, repository: StateRepository) -> dict:
    current_time = time.time()
    state = repository.get(camera_id)

    if analysis["has_pet"] and analysis["position"]:
        if state["last_position"]:
            rate = movement_rate(state["last_position"], analysis["position"])
            analysis["is_moving"] = is_moving_by_rate(rate)
            if analysis["is_moving"]:
                state["stationary_start_time"] = current_time

        state["last_position"] = analysis["position"]

        if state["food_bowl_position"]:
            if is_in_food_bowl(analysis["position"], state["food_bowl_position"]):
                state["last_eating_time"] = current_time
                analysis["is_eating"] = True
            else:
                analysis["is_eating"] = False
        else:
            analysis["is_eating"] = False

    stationary_duration = current_time - state["stationary_start_time"]
    analysis["anomaly"]["long_stationary"] = stationary_duration > settings.stationary_threshold

    no_eating_duration = current_time - state["last_eating_time"]
    analysis["anomaly"]["no_eating"] = no_eating_duration > settings.no_eating_threshold

    if "food_status" not in analysis:
        analysis["food_status"] = "unknown"

    state["history"].append(
        {
            "timestamp": current_time,
            "has_pet": analysis["has_pet"],
            "position": analysis["position"],
            "is_moving": analysis.get("is_moving", False),
            "is_eating": analysis.get("is_eating", False),
            "food_status": analysis["food_status"],
            "confidence": analysis["confidence"],
        }
    )
    if len(state["history"]) > settings.max_history:
        state["history"] = state["history"][-settings.max_history :]

    state["total_analyses"] += 1
    state["last_activity_time"] = current_time

    return analysis

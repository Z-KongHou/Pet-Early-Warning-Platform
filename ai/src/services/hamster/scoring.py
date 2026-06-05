def calculate_activity_score(analysis: dict) -> int:
    score = 50

    if analysis.get("has_pet", False):
        score += 20

    if analysis.get("is_moving", False):
        score += 25
    else:
        score -= 15

    if analysis.get("food_status") == "食盆不空":
        score += 10

    if analysis.get("anomaly", {}).get("long_stationary", False):
        score -= 20

    return max(0, min(100, score))


def get_activity_status(score: int) -> str:
    if score >= 70:
        return "normal"
    if score >= 40:
        return "low"
    return "critical"


def get_activity_description(score: int) -> str:
    if score >= 80:
        return "仓鼠活动频繁，较为活跃"
    if score >= 60:
        return "仓鼠活动正常"
    if score >= 40:
        return "仓鼠活动较少，建议关注"
    return "仓鼠活动异常，需要检查"


def get_analysis_result(analysis: dict) -> str:
    if not analysis.get("has_pet", False):
        return "未检测到仓鼠"

    result = "仓鼠"

    if analysis.get("is_moving", False):
        result += "正在活动中"
    else:
        result += "处于静止状态"

    food_status = analysis.get("food_status", "unknown")
    if food_status == "食盆不空":
        result += "，食盆中有食物"
    elif food_status == "食盆为空":
        result += "，食盆为空"

    if analysis.get("anomaly", {}).get("long_stationary", False):
        result += "，已长时间未移动"

    if analysis.get("anomaly", {}).get("no_eating", False):
        result += "，已长时间未进食"

    return result

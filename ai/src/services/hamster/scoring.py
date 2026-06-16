from config import settings


# ---------------------------------------------------------------------------
# 各维度子得分计算（全部基于连续实测值，归一化到 0-100）
# ---------------------------------------------------------------------------

def _compute_movement_score(movement_ratio: float) -> float:
    """运动活跃度：多帧移动比例（0~1）→ 0-100"""
    return round(movement_ratio * 100, 2)


def _compute_food_score(blue_ratio: float | None) -> float:
    """食盆状态：蓝色像素占比越低=食物越多=分数越高

    blue_ratio 是食盆区域内蓝色像素的比例（0~1）:
      - 接近 0  → 食盆被食物覆盖，几乎看不到蓝色 → 高分
      - 接近 1  → 食盆空，大量蓝色露出           → 低分
      - None    → 未配置食盆区域，无法判断         → 回退 50
    """
    if blue_ratio is None:
        return 50.0
    return round((1.0 - blue_ratio) * 100, 2)


def _compute_presence_score(confidence: float, pet_frame_ratio: float) -> float:
    """宠物存在度：检测置信度 × 有宠帧占比 → 0-100

    confidence:       API 返回的平均检测置信度 (0~1)
    pet_frame_ratio:  检测到仓鼠的帧数 / 总分析帧数 (0~1)

    两个因子相乘，任何一个为 0 都会把存在分拉低。
    """
    return round(confidence * pet_frame_ratio * 100, 2)


def _compute_anomaly_free_score(anomaly: dict) -> float:
    """无异常程度：按实际持续时长比例扣分，而非布尔跳变

    - 静止时间占阈值的比例 × 60 分扣减
    - 未进食时间占阈值的比例 × 40 分扣减
    - 例如: 静止 30s（阈值 60s → 50%），扣 30 分而非 60 分
    """
    score = 100.0

    stationary_duration = anomaly.get("stationary_duration", 0)
    if stationary_duration > 0:
        stationary_ratio = min(stationary_duration / settings.stationary_threshold, 1.0)
        score -= 60 * stationary_ratio

    no_eating_duration = anomaly.get("no_eating_duration", 0)
    if no_eating_duration > 0:
        eating_ratio = min(no_eating_duration / settings.no_eating_threshold, 1.0)
        score -= 40 * eating_ratio

    return max(0.0, round(score, 2))


# ---------------------------------------------------------------------------
# 加权总分
# ---------------------------------------------------------------------------

def calculate_activity_score(
    analysis: dict,
    movement_ratio: float = 0.0,
    pet_frame_ratio: float = 0.0,
) -> int:
    """百分比加权制活动评分（全部连续值）

    四维权重（可通过环境变量覆盖）：
      - movement   (运动活跃度) : 默认 40%
      - food       (食盆状态)   : 默认 25%
      - presence   (宠物存在)   : 默认 20%
      - anomaly    (无异常程度) : 默认 15%

    公式: score = w1*m + w2*f + w3*p + w4*a，最终 clamp 到 [0, 100]
    """
    movement_score = _compute_movement_score(movement_ratio)
    food_score = _compute_food_score(analysis.get("blue_ratio"))
    presence_score = _compute_presence_score(
        analysis.get("confidence", 0.0), pet_frame_ratio
    )
    anomaly_score = _compute_anomaly_free_score(analysis.get("anomaly", {}))

    weighted = (
        settings.activity_weight_movement * movement_score
        + settings.activity_weight_food * food_score
        + settings.activity_weight_presence * presence_score
        + settings.activity_weight_anomaly * anomaly_score
    )

    return max(0, min(100, round(weighted)))


# ---------------------------------------------------------------------------
# 状态 / 描述映射（不变）
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 快速验证
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("Continuous weighted activity scoring - verification")
    print(f"Weights: movement={settings.activity_weight_movement}, "
          f"food={settings.activity_weight_food}, "
          f"presence={settings.activity_weight_presence}, "
          f"anomaly={settings.activity_weight_anomaly}")
    print(f"Thresholds: stationary={settings.stationary_threshold}s, "
          f"no_eating={settings.no_eating_threshold}s")
    print("=" * 70)

    # Test 1: Continuity - same scenario, slightly different inputs should give slightly different scores
    print("\n-- Continuity: sliding food (blue_ratio 0.1 -> 0.9) --")
    for blue in [0.1, 0.3, 0.5, 0.7, 0.9]:
        analysis = {"blue_ratio": blue, "confidence": 0.9, "anomaly": {}}
        score = calculate_activity_score(analysis, movement_ratio=0.5, pet_frame_ratio=0.8)
        print(f"  blue_ratio={blue} -> food_sub={_compute_food_score(blue):.0f} -> score={score}")

    print("\n-- Continuity: sliding movement (ratio 0.0 -> 1.0) --")
    for mr in [0.0, 0.25, 0.5, 0.75, 1.0]:
        analysis = {"blue_ratio": 0.3, "confidence": 0.9, "anomaly": {}}
        score = calculate_activity_score(analysis, movement_ratio=mr, pet_frame_ratio=0.8)
        print(f"  movement_ratio={mr} -> movement_sub={_compute_movement_score(mr):.0f} -> score={score}")

    print("\n-- Continuity: sliding presence (confidence x pet_frame_ratio) --")
    for conf, pfr in [(0.95, 1.0), (0.8, 0.8), (0.6, 0.6), (0.4, 0.4), (0.2, 0.2)]:
        analysis = {"blue_ratio": 0.3, "confidence": conf, "anomaly": {}}
        score = calculate_activity_score(analysis, movement_ratio=0.5, pet_frame_ratio=pfr)
        ps = _compute_presence_score(conf, pfr)
        print(f"  conf={conf} pfr={pfr} -> presence_sub={ps:.0f} -> score={score}")

    print("\n-- Continuity: sliding anomaly (stationary duration 0 -> 90s) --")
    for dur in [0, 15, 30, 45, 60, 90]:
        anomaly = {"stationary_duration": dur}
        analysis = {"blue_ratio": 0.3, "confidence": 0.9, "anomaly": anomaly}
        score = calculate_activity_score(analysis, movement_ratio=0.5, pet_frame_ratio=0.8)
        asym = _compute_anomaly_free_score(anomaly)
        print(f"  stationary={dur}s -> anomaly_sub={asym:.0f} -> score={score}")

    print("\n-- Scenario: best case --")
    s = calculate_activity_score(
        {"blue_ratio": 0.05, "confidence": 0.98, "anomaly": {}},
        movement_ratio=0.95, pet_frame_ratio=1.0,
    )
    print(f"  Best: score={s} status={get_activity_status(s)}")

    print("\n-- Scenario: worst case --")
    s = calculate_activity_score(
        {"blue_ratio": 0.98, "confidence": 0.1, "anomaly": {"stationary_duration": 120, "no_eating_duration": 200}},
        movement_ratio=0.0, pet_frame_ratio=0.1,
    )
    print(f"  Worst: score={s} status={get_activity_status(s)}")

    print("\n" + "=" * 70)
    print("Done - all scores should slide smoothly without sudden jumps.")

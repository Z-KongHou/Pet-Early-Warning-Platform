"""领域模型：实体与值对象（当前分析流程以 dict 快照传递，此处作类型约定）。"""

from typing import Any, TypedDict


class PositionDict(TypedDict):
    x: float
    y: float
    width: float
    height: float


class BowlRectDict(TypedDict):
    x: int
    y: int
    width: int
    height: int


class AnomalyDict(TypedDict):
    long_stationary: bool
    no_eating: bool


class AnalysisDict(TypedDict, total=False):
    has_pet: bool
    pet_type: str
    position: PositionDict | None
    is_moving: bool
    is_eating: bool
    food_status: str
    blue_ratio: float | None
    anomaly: AnomalyDict
    confidence: float


class CameraStateDict(TypedDict, total=False):
    last_position: PositionDict | None
    last_eating_time: float
    stationary_start_time: float
    food_bowl_position: BowlRectDict | None
    history: list[dict[str, Any]]
    total_analyses: int
    last_activity_time: float

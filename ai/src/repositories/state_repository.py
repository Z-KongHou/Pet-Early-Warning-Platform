"""Pet state repository — 委托给后端 REST API 读写 MySQL。"""

from __future__ import annotations

from typing import Any

from clients.backend_client import BackendClient


class BackendStateRepository:
    """通过后端 REST API 管理每摄像头的宠物状态。"""

    def __init__(self, backend_client: BackendClient) -> None:
        self._client = backend_client

    def get(self, camera_id: str) -> dict[str, Any]:
        """获取摄像头状态（不存在则后端自动创建），返回兼容格式的 dict。"""
        state = self._client.get_pet_state(camera_id, user_id=1)
        state["_camera_id"] = camera_id
        return state

    def set_bowl_position(self, camera_id: str, bowl: dict[str, int]) -> None:
        """更新食盆位置。"""
        self._client.update_pet_state(camera_id, {"food_bowl_position": bowl})

    def save_state(self, camera_id: str, state: dict[str, Any]) -> None:
        """将内存中修改过的状态持久化到后端。"""
        updates: dict[str, Any] = {}

        if "last_position" in state:
            updates["last_position"] = state["last_position"]
        if "food_bowl_position" in state:
            updates["food_bowl_position"] = state["food_bowl_position"]
        if "last_eating_time" in state:
            updates["last_eating_time"] = state["last_eating_time"]
        if "stationary_start_time" in state:
            updates["stationary_start_time"] = state["stationary_start_time"]
        if "total_analyses" in state:
            updates["total_analyses"] = state["total_analyses"]

        if updates:
            self._client.update_pet_state(camera_id, updates)

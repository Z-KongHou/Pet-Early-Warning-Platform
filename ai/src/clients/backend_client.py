"""通过后端 REST API 读写 MySQL 数据，替代直接 SQLite/内存访问。"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class BackendClient:
    """封装对 Spring Boot 后端 /api/internal/* 接口的 HTTP 调用。"""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self._base_url = (base_url or settings.backend_url).rstrip("/")
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout)

    # ==================== frame_images ====================

    def insert_frame(
        self,
        user_id: int,
        camera_id: str,
        request_id: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        image_timestamp: float,
        source: str = "upload",
    ) -> int | None:
        """插入帧记录，返回帧 ID。"""
        body = {
            "user_id": user_id,
            "camera_id": camera_id,
            "request_id": request_id,
            "original_filename": original_filename,
            "file_path": file_path,
            "file_size": file_size,
            "image_timestamp": datetime.fromtimestamp(image_timestamp).isoformat(),
            "source": source,
        }
        try:
            with self._client() as client:
                resp = client.post(self._url("/api/internal/frames"), json=body)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    return data["data"]["id"]
                logger.error("insert_frame failed: %s", data)
                return None
        except Exception as exc:
            logger.error("insert_frame error: %s", exc)
            return None

    def get_frame_by_id(self, frame_id: int) -> dict[str, Any] | None:
        """按 ID 查询帧。"""
        try:
            with self._client() as client:
                resp = client.get(self._url(f"/api/internal/frames/{frame_id}"))
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    return data["data"]
                return None
        except Exception as exc:
            logger.error("get_frame_by_id error: %s", exc)
            return None

    def get_frames_in_window(
        self, camera_id: str, latest_ts: float, window_seconds: int
    ) -> list[dict[str, Any]]:
        """查询时间窗口内的帧。"""
        params = {
            "camera_id": camera_id,
            "latest_ts": datetime.fromtimestamp(latest_ts).isoformat(),
            "window_seconds": window_seconds,
        }
        try:
            with self._client() as client:
                resp = client.get(self._url("/api/internal/frames/window"), params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    return data["data"]["frames"]
                return []
        except Exception as exc:
            logger.error("get_frames_in_window error: %s", exc)
            return []

    def get_latest_detected_frame(
        self, camera_id: str, before_ts: float
    ) -> dict[str, Any] | None:
        """查询最近一次检测到宠物的帧。"""
        params = {
            "camera_id": camera_id,
            "before_ts": datetime.fromtimestamp(before_ts).isoformat(),
        }
        try:
            with self._client() as client:
                resp = client.get(
                    self._url("/api/internal/frames/latest-detected"), params=params
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    frame = data["data"]["frame"]
                    return frame
                return None
        except Exception as exc:
            logger.error("get_latest_detected_frame error: %s", exc)
            return None

    def update_frame_detection(
        self,
        frame_id: int,
        has_pet: bool,
        position: dict[str, int] | None,
        confidence: float,
        food_status: str,
    ) -> None:
        """更新帧的检测结果。"""
        body: dict[str, Any] = {
            "has_pet": has_pet,
            "confidence": confidence,
            "food_status": food_status,
        }
        if position:
            body["position"] = {
                "x": position.get("x"),
                "y": position.get("y"),
                "width": position.get("width"),
                "height": position.get("height"),
            }
        try:
            with self._client() as client:
                resp = client.put(
                    self._url(f"/api/internal/frames/{frame_id}/detection"), json=body
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("update_frame_detection error: %s", exc)

    def batch_update_status(self, frame_ids: list[int], status: str) -> None:
        """批量更新帧状态。"""
        if not frame_ids:
            return
        body = {"frame_ids": frame_ids, "status": status}
        try:
            with self._client() as client:
                resp = client.put(
                    self._url("/api/internal/frames/batch-status"), json=body
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("batch_update_status error: %s", exc)

    def batch_touch_frames(self, frame_ids: list[int]) -> None:
        """批量更新 last_accessed_at。"""
        if not frame_ids:
            return
        body = {"frame_ids": frame_ids}
        try:
            with self._client() as client:
                resp = client.put(
                    self._url("/api/internal/frames/batch-touch"), json=body
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("batch_touch_frames error: %s", exc)

    def evict_lru_frames(self, camera_id: str) -> None:
        """LRU 淘汰旧帧。"""
        try:
            with self._client() as client:
                resp = client.post(
                    self._url("/api/internal/frames/evict"),
                    params={"camera_id": camera_id},
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("evict_lru_frames error: %s", exc)

    # ==================== pet_state ====================

    def get_pet_state(self, camera_id: str, user_id: int = 1) -> dict[str, Any]:
        """获取摄像头状态（不存在则自动创建）。"""
        try:
            with self._client() as client:
                resp = client.get(
                    self._url("/api/internal/pet-state"),
                    params={"camera_id": camera_id, "user_id": user_id},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    return _convert_state(data["data"])
                return _default_state()
        except Exception as exc:
            logger.error("get_pet_state error: %s", exc)
            return _default_state()

    def update_pet_state(self, camera_id: str, updates: dict[str, Any]) -> None:
        """更新摄像头状态。"""
        db_updates: dict[str, Any] = {}
        for key, value in updates.items():
            if key == "last_position" and isinstance(value, dict):
                db_updates["last_position_x"] = value.get("x")
                db_updates["last_position_y"] = value.get("y")
                db_updates["last_position_width"] = value.get("width")
                db_updates["last_position_height"] = value.get("height")
            elif key == "food_bowl_position" and isinstance(value, dict):
                db_updates["food_bowl_position_x"] = value.get("x")
                db_updates["food_bowl_position_y"] = value.get("y")
                db_updates["food_bowl_position_width"] = value.get("width")
                db_updates["food_bowl_position_height"] = value.get("height")
            elif key == "last_eating_time" and isinstance(value, (int, float)):
                db_updates["last_eating_time"] = datetime.fromtimestamp(value).isoformat()
            elif key == "stationary_start_time" and isinstance(value, (int, float)):
                db_updates["stationary_start_time"] = datetime.fromtimestamp(value).isoformat()
            elif key == "total_analyses":
                db_updates["total_analyses"] = value

        if not db_updates:
            return
        try:
            with self._client() as client:
                resp = client.put(
                    self._url("/api/internal/pet-state"),
                    params={"camera_id": camera_id},
                    json=db_updates,
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("update_pet_state error: %s", exc)

    # ==================== pet_analysis ====================

    def get_analysis_history(self, camera_id: str) -> list[dict[str, Any]]:
        """查询分析历史。"""
        try:
            with self._client() as client:
                resp = client.get(
                    self._url("/api/internal/pet-analysis/history"),
                    params={"camera_id": camera_id},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    return data["data"]["history"]
                return []
        except Exception as exc:
            logger.error("get_analysis_history error: %s", exc)
            return []

    # ==================== SQL query ====================

    def execute_query(self, sql: str) -> dict[str, Any]:
        """Execute a read-only SELECT SQL query via the backend.

        The Authorization header from the original request is forwarded
        so the backend can validate the JWT and extract user_id.

        Returns: {"rows": [...], "count": N} on success,
                 or {"error": "message"} on rejection/error.
        """
        from utils.auth import get_current_token

        headers = {}
        token = get_current_token()
        if token:
            headers["Authorization"] = token

        try:
            with self._client() as client:
                resp = client.post(
                    self._url("/api/internal/query"),
                    json={"sql": sql},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    rows = data.get("data", [])
                    return {"rows": rows, "count": len(rows)}
                return {"error": data.get("message", "Query rejected")}
        except Exception as exc:
            logger.error("execute_query error: %s", exc)
            return {"error": str(exc)}

    # ==================== agent context ====================

    def get_agent_context(self, user_id: int = 1) -> dict[str, Any]:
        """获取 AI agent 所需的非敏感数据库上下文：仓鼠、摄像头、设置。"""
        try:
            with self._client() as client:
                resp = client.get(
                    self._url("/api/internal/agent-context"),
                    params={"user_id": user_id},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    return data["data"]
                logger.error("get_agent_context failed: %s", data)
                return {"hamsters": [], "cameras": [], "settings": {}}
        except Exception as exc:
            logger.error("get_agent_context error: %s", exc)
            return {"hamsters": [], "cameras": [], "settings": {}}


def _default_state() -> dict[str, Any]:
    """返回默认的空状态（兼容 MemoryStateRepository 格式）。"""
    now = time.time()
    return {
        "last_position": None,
        "last_eating_time": now,
        "stationary_start_time": now,
        "food_bowl_position": None,
        "history": [],
        "total_analyses": 0,
    }


def _convert_state(raw: dict[str, Any]) -> dict[str, Any]:
    """将后端返回的 pet_state 转为 AI 服务使用的格式。"""
    now = time.time()
    state: dict[str, Any] = {
        "last_position": raw.get("last_position"),
        "last_eating_time": _parse_dt_or(raw, "last_eating_time", now),
        "stationary_start_time": _parse_dt_or(raw, "stationary_start_time", now),
        "food_bowl_position": raw.get("food_bowl_position"),
        "history": raw.get("history", []),
        "total_analyses": raw.get("total_analyses", 0),
    }
    return state


def _parse_dt_or(raw: dict[str, Any], key: str, default: float) -> float:
    """尝试将 ISO 格式字符串转为 timestamp，失败则返回默认值。"""
    val = raw.get(key)
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).timestamp()
        except ValueError:
            return default
    return default

"""Frame repository — 委托给后端 REST API 读写 MySQL。"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from clients.backend_client import BackendClient
from config import settings


class BackendFrameRepository:
    """通过后端 REST API 管理帧数据，本地仅负责文件 I/O。"""

    def __init__(self, backend_client: BackendClient) -> None:
        self._client = backend_client
        self._base_dir = settings.base_dir
        settings.upload_dir.mkdir(parents=True, exist_ok=True)

    def init_schema(self) -> None:
        """表已由 MySQL 迁移文件创建，无需操作。"""
        pass

    # ---- 文件 I/O（保留本地） ----

    def save_upload(self, camera_id: str, index: int, filename: str, image_bytes: bytes) -> str:
        safe_name = os.path.basename(filename or "capture.jpg")
        for ch in '<>:"/\\|?*':
            safe_name = safe_name.replace(ch, "_")
        out_name = f"{camera_id}_{int(time.time() * 1000)}_{index}_{safe_name}"
        out_path = settings.upload_dir / out_name
        out_path.write_bytes(image_bytes)
        return str(out_path.relative_to(self._base_dir)).replace("\\", "/")

    def read_file_bytes(self, file_path: str) -> bytes:
        abs_path = self._base_dir / Path(file_path)
        return abs_path.read_bytes()

    # ---- 数据库操作（委托给后端 API） ----

    def insert_frame(
        self,
        camera_id: str,
        request_id: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        image_timestamp: float,
        source: str = "upload",
    ) -> int:
        frame_id = self._client.insert_frame(
            user_id=1,
            camera_id=camera_id,
            request_id=request_id,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            image_timestamp=image_timestamp,
            source=source,
        )
        return frame_id or 0

    def get_frame_by_id(self, frame_id: int) -> dict[str, Any] | None:
        frame = self._client.get_frame_by_id(frame_id)
        return _normalize_frame(frame) if frame else None

    def get_frames_in_window(
        self, camera_id: str, latest_ts: float, window_seconds: int
    ) -> list[dict[str, Any]]:
        frames = self._client.get_frames_in_window(camera_id, latest_ts, window_seconds)
        result = [_normalize_frame(f) for f in frames]
        self.touch_frames([f["id"] for f in result])
        return result

    def touch_frames(self, frame_ids: list[int]) -> None:
        if not frame_ids:
            return
        self._client.batch_touch_frames(frame_ids)

    def mark_frames_status(self, frame_ids: list[int], status: str) -> None:
        if not frame_ids:
            return
        self._client.batch_update_status(frame_ids, status)

    def evict_lru_frames(self, camera_id: str) -> None:
        self._client.evict_lru_frames(camera_id)

    def update_frame_detection(self, frame_id: int, analysis: dict[str, Any]) -> None:
        self._client.update_frame_detection(
            frame_id=frame_id,
            has_pet=analysis.get("has_pet", False),
            position=analysis.get("position"),
            confidence=analysis.get("confidence", 0.0),
            food_status=analysis.get("food_status", "unknown"),
        )

    def get_latest_detected_frame(
        self, camera_id: str, before_ts: float
    ) -> dict[str, Any] | None:
        frame = self._client.get_latest_detected_frame(camera_id, before_ts)
        if frame:
            result = _normalize_frame(frame)
            self.touch_frames([result["id"]])
            return result
        return None

    def insert_analysis_record(
        self, camera_id: str, timestamp_value: float, analysis: dict[str, Any]
    ) -> None:
        """分析记录已由后端 FrameCaptureService 保存，此处无需重复写入。"""
        pass

    def get_all_history(self, camera_id: str) -> list[dict[str, Any]]:
        history = self._client.get_analysis_history(camera_id)
        return [_normalize_history_record(r) for r in history]


def _parse_timestamp_to_float(ts: Any) -> float:
    """将 ISO 格式字符串或已有的 float 转为 Unix epoch float。"""
    if ts is None:
        return time.time()
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts).timestamp()
        except ValueError:
            return time.time()
    return time.time()


def _normalize_frame(raw: dict[str, Any]) -> dict[str, Any]:
    """将后端返回的帧数据转为 AI 服务内部格式（timestamp 统一为 float）。"""
    ts = _parse_timestamp_to_float(raw.get("image_timestamp") or raw.get("timestamp"))

    position = raw.get("position")
    analysis = raw.get("analysis")
    if analysis is None and raw.get("has_pet") is not None:
        analysis = {
            "has_pet": bool(raw.get("has_pet")),
            "pet_type": "仓鼠",
            "position": position,
            "confidence": raw.get("confidence", 0.0),
            "food_status": raw.get("food_status", "unknown"),
            "is_moving": False,
            "anomaly": {"long_stationary": False, "no_eating": False},
        }

    return {
        "id": raw["id"],
        "camera_id": raw.get("camera_id", ""),
        "request_id": raw.get("request_id", ""),
        "filename": raw.get("filename") or raw.get("original_filename", ""),
        "file_path": raw.get("file_path", ""),
        "file_size": raw.get("file_size", 0),
        "timestamp": ts,
        "image_timestamp": ts,
        "source": raw.get("source", "upload"),
        "status": raw.get("status", "stored"),
        "position": position,
        "analysis": analysis,
    }


def _normalize_history_record(raw: dict[str, Any]) -> dict[str, Any]:
    """将后端返回的 pet_analysis 记录转为 AI 服务内部格式。"""
    ts = _parse_timestamp_to_float(raw.get("timestamp"))

    position = raw.get("position")
    return {
        "id": raw.get("id"),
        "camera_id": raw.get("camera_id", ""),
        "timestamp": ts,
        "has_pet": raw.get("has_pet", False),
        "movement_state": raw.get("movement_state", "stationary"),
        "is_moving": raw.get("is_moving", False),
        "food_state": raw.get("food_state", "unknown"),
        "position": position,
        "confidence": raw.get("confidence", 0.0),
    }

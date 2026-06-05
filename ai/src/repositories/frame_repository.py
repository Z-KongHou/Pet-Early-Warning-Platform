import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from config import settings


class SQLiteFrameRepository:
    def __init__(self) -> None:
        self._db_path = settings.database_path
        self._base_dir = settings.base_dir
        settings.upload_dir.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def init_schema(self) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pet_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                has_pet INTEGER NOT NULL,
                movement_state TEXT DEFAULT 'stationary',
                food_state TEXT DEFAULT 'unknown',
                position_x INTEGER,
                position_y INTEGER,
                position_width INTEGER,
                position_height INTEGER,
                confidence REAL,
                created_at REAL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_camera_timestamp ON pet_analysis(camera_id, timestamp)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS frame_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                original_filename TEXT,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                image_timestamp REAL NOT NULL,
                source TEXT DEFAULT 'upload',
                status TEXT DEFAULT 'stored',
                last_accessed_at REAL NOT NULL,
                created_at REAL DEFAULT CURRENT_TIMESTAMP,
                has_pet INTEGER,
                position_x INTEGER,
                position_y INTEGER,
                position_width INTEGER,
                position_height INTEGER,
                confidence REAL,
                food_status TEXT,
                analyzed_at REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_frame_camera_ts ON frame_images(camera_id, image_timestamp)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_frame_camera_lru ON frame_images(camera_id, last_accessed_at)
            """
        )
        conn.commit()
        conn.close()

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
        now = time.time()
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO frame_images (
                camera_id, request_id, original_filename, file_path, file_size,
                image_timestamp, source, status, last_accessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'stored', ?)
            """,
            (camera_id, request_id, original_filename, file_path, file_size, image_timestamp, source, now),
        )
        frame_id = int(cursor.lastrowid)
        conn.commit()
        conn.close()
        return frame_id

    def _frame_dict_from_row(self, row: tuple[Any, ...]) -> dict[str, Any]:
        position = None
        if row[12] is not None:
            position = {"x": row[12], "y": row[13], "width": row[14], "height": row[15]}

        analysis = None
        if row[18] is not None:
            analysis = {
                "has_pet": bool(row[11]),
                "pet_type": "仓鼠",
                "position": position,
                "confidence": row[16] or 0.0,
                "food_status": row[17] or "unknown",
                "is_moving": False,
                "anomaly": {"long_stationary": False, "no_eating": False},
            }

        return {
            "id": row[0],
            "camera_id": row[1],
            "request_id": row[2],
            "filename": row[3],
            "file_path": row[4],
            "file_size": row[5],
            "timestamp": row[6],
            "image_timestamp": row[6],
            "source": row[7],
            "status": row[8],
            "last_accessed_at": row[9],
            "position": position,
            "analysis": analysis,
        }

    def get_frame_by_id(self, frame_id: int) -> dict[str, Any] | None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM frame_images WHERE id = ?", (frame_id,))
        row = cursor.fetchone()
        conn.close()
        return self._frame_dict_from_row(row) if row else None

    def get_frames_in_window(self, camera_id: str, latest_ts: float, window_seconds: int) -> list[dict[str, Any]]:
        min_ts = latest_ts - window_seconds
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM frame_images
            WHERE camera_id = ? AND image_timestamp >= ? AND image_timestamp <= ?
            ORDER BY image_timestamp ASC
            """,
            (camera_id, min_ts, latest_ts),
        )
        rows = cursor.fetchall()
        conn.close()
        frames = [self._frame_dict_from_row(row) for row in rows]
        self.touch_frames([f["id"] for f in frames])
        return frames

    def touch_frames(self, frame_ids: list[int]) -> None:
        if not frame_ids:
            return
        now = time.time()
        conn = self._connect()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(frame_ids))
        cursor.execute(
            f"UPDATE frame_images SET last_accessed_at = ? WHERE id IN ({placeholders})",
            [now, *frame_ids],
        )
        conn.commit()
        conn.close()

    def mark_frames_status(self, frame_ids: list[int], status: str) -> None:
        if not frame_ids:
            return
        conn = self._connect()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(frame_ids))
        cursor.execute(
            f"UPDATE frame_images SET status = ? WHERE id IN ({placeholders})",
            [status, *frame_ids],
        )
        conn.commit()
        conn.close()

    def evict_lru_frames(self, camera_id: str) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM frame_images WHERE camera_id = ?", (camera_id,))
        count = cursor.fetchone()[0]
        if count <= settings.max_frames_per_camera:
            conn.close()
            return

        excess = count - settings.max_frames_per_camera
        cursor.execute(
            """
            SELECT id, file_path FROM frame_images
            WHERE camera_id = ?
            ORDER BY last_accessed_at ASC
            LIMIT ?
            """,
            (camera_id, excess),
        )
        rows = cursor.fetchall()
        for _, rel_path in rows:
            abs_path = self._base_dir / Path(rel_path)
            if abs_path.is_file():
                try:
                    abs_path.unlink()
                except OSError:
                    pass

        ids = [row[0] for row in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            cursor.execute(f"DELETE FROM frame_images WHERE id IN ({placeholders})", ids)
            conn.commit()
        conn.close()

    def update_frame_detection(self, frame_id: int, analysis: dict[str, Any]) -> None:
        position = analysis.get("position") or {}
        now = time.time()
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE frame_images SET
                status = 'analyzed',
                has_pet = ?,
                position_x = ?, position_y = ?, position_width = ?, position_height = ?,
                confidence = ?, food_status = ?, analyzed_at = ?,
                last_accessed_at = ?
            WHERE id = ?
            """,
            (
                1 if analysis.get("has_pet") else 0,
                position.get("x"),
                position.get("y"),
                position.get("width"),
                position.get("height"),
                analysis.get("confidence", 0),
                analysis.get("food_status", "unknown"),
                now,
                now,
                frame_id,
            ),
        )
        conn.commit()
        conn.close()

    def get_latest_detected_frame(self, camera_id: str, before_ts: float) -> dict[str, Any] | None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM frame_images
            WHERE camera_id = ? AND has_pet = 1
              AND position_x IS NOT NULL AND analyzed_at IS NOT NULL
              AND image_timestamp < ?
            ORDER BY image_timestamp DESC
            LIMIT 1
            """,
            (camera_id, before_ts),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        frame = self._frame_dict_from_row(row)
        self.touch_frames([frame["id"]])
        return frame

    def insert_analysis_record(self, camera_id: str, timestamp_value: float, analysis: dict[str, Any]) -> None:
        position = analysis.get("position") or {}
        movement_state = "moving" if analysis.get("is_moving", False) else "stationary"
        food_status = analysis.get("food_status", "unknown")
        food_state = "present" if food_status == "食盆不空" else ("empty" if food_status == "食盆为空" else "unknown")

        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pet_analysis (
                camera_id, timestamp, has_pet, movement_state, food_state,
                position_x, position_y, position_width, position_height, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camera_id,
                timestamp_value,
                1 if analysis.get("has_pet", False) else 0,
                movement_state,
                food_state,
                position.get("x"),
                position.get("y"),
                position.get("width"),
                position.get("height"),
                analysis.get("confidence", 0),
            ),
        )
        conn.commit()
        cursor.execute(
            """
            DELETE FROM pet_analysis
            WHERE camera_id = ?
            AND id NOT IN (
                SELECT id FROM pet_analysis WHERE camera_id = ? ORDER BY timestamp DESC LIMIT ?
            )
            """,
            (camera_id, camera_id, settings.max_history_records),
        )
        conn.commit()
        conn.close()

    def get_all_history(self, camera_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM pet_analysis
            WHERE camera_id = ?
            ORDER BY timestamp ASC
            """,
            (camera_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        history: list[dict[str, Any]] = []
        for row in rows:
            history.append(
                {
                    "id": row[0],
                    "camera_id": row[1],
                    "timestamp": row[2],
                    "has_pet": bool(row[3]),
                    "movement_state": row[4],
                    "is_moving": row[4] == "moving",
                    "food_state": row[5],
                    "position": {"x": row[6], "y": row[7], "width": row[8], "height": row[9]}
                    if row[6] is not None
                    else None,
                    "confidence": row[10],
                }
            )
        return history

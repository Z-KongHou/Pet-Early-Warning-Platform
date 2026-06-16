import base64
import random
import time
import uuid
from typing import Any

from fastapi import HTTPException

from clients.ezviz_client import EzvizClient
from clients.image_processor import compress_image
from clients.timestamp_extractor import TimestampExtractor
from config import settings
from repositories.frame_repository import BackendFrameRepository
from repositories.protocols import StateRepository
from repositories.state_repository import BackendStateRepository
from services.hamster.analysis import update_pet_state
from services.hamster.bowl import analyze_bowl, is_in_food_bowl
from services.hamster.detection import parse_pet_detection
from services.hamster.movement import is_moving_by_rate, movement_rate
from services.hamster.scoring import (
    calculate_activity_score,
    get_activity_description,
    get_activity_status,
    get_analysis_result,
)


def _format_analyze_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        return detail if isinstance(detail, str) else str(detail)
    return str(exc)


def sample_frame_records(frames: list[dict[str, Any]], max_count: int) -> tuple[list[dict[str, Any]], bool]:
    if len(frames) <= max_count:
        return frames, False
    return random.sample(frames, max_count), True


def compare_frames_movement(frames: list[dict[str, Any]]) -> dict[str, Any]:
    pet_frames = sorted(
        [f for f in frames if f.get("analysis", {}).get("has_pet") and f.get("analysis", {}).get("position")],
        key=lambda f: f["timestamp"],
    )
    rates: list[float] = []
    moving_pairs = 0
    for i in range(1, len(pet_frames)):
        rate = movement_rate(pet_frames[i - 1]["analysis"]["position"], pet_frames[i]["analysis"]["position"])
        rates.append(rate)
        if is_moving_by_rate(rate):
            moving_pairs += 1

    total_pairs = len(rates)
    return {
        "total_pairs": total_pairs,
        "moving_pairs": moving_pairs,
        "movement_ratio": round(moving_pairs / total_pairs, 4) if total_pairs else 0.0,
        "max_movement_rate": round(max(rates), 4) if rates else 0.0,
        "avg_movement_rate": round(sum(rates) / len(rates), 4) if rates else 0.0,
        "is_moving": moving_pairs > 0,
    }


def build_unified_analysis(frames: list[dict[str, Any]], movement_info: dict[str, Any]) -> dict[str, Any]:
    successful = [f for f in frames if f.get("analysis")]
    pet_frames = [f for f in successful if f["analysis"].get("has_pet")]
    latest_success = max(successful, key=lambda f: f["timestamp"]) if successful else None
    latest_pet = max(pet_frames, key=lambda f: f["timestamp"]) if pet_frames else None
    source = latest_pet or latest_success
    base = source["analysis"] if source else parse_pet_detection({})

    confidences = [f["analysis"]["confidence"] for f in pet_frames if f["analysis"].get("confidence")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else base.get("confidence", 0.0)

    food_votes: dict[str, int] = {}
    for frame in successful:
        status = frame["analysis"].get("food_status", "unknown")
        if status != "unknown":
            food_votes[status] = food_votes.get(status, 0) + 1
    food_status = max(food_votes, key=food_votes.get) if food_votes else base.get("food_status", "unknown")

    in_bowl_count = sum(1 for frame in pet_frames if frame["analysis"].get("is_in_food_bowl"))
    is_in_food_bowl_majority = in_bowl_count > len(pet_frames) / 2 if pet_frames else False

    return {
        "has_pet": len(pet_frames) > 0,
        "pet_type": "仓鼠",
        "position": latest_pet["analysis"]["position"] if latest_pet else None,
        "is_moving": movement_info["is_moving"],
        "is_in_food_bowl": is_in_food_bowl_majority,
        "food_status": food_status,
        "anomaly": {"long_stationary": False, "no_eating": False},
        "confidence": avg_confidence,
        "blue_ratio": base.get("blue_ratio"),
    }


class AnalyzeHamsterUseCase:
    def __init__(
        self,
        ezviz: EzvizClient,
        state_repository: StateRepository,
        frame_repository: BackendFrameRepository,
        timestamp_extractor: TimestampExtractor,
    ) -> None:
        self._ezviz = ezviz
        self._state_repository = state_repository
        self._frame_repository = frame_repository
        self._timestamp_extractor = timestamp_extractor

    def _compare_movement_fallback(self, analysis: dict[str, Any], camera_id: str, before_ts: float) -> bool:
        if not analysis.get("has_pet") or not analysis.get("position"):
            return False

        prev_frame = self._frame_repository.get_latest_detected_frame(camera_id, before_ts)
        if prev_frame and prev_frame.get("position"):
            rate = movement_rate(prev_frame["position"], analysis["position"])
            if is_moving_by_rate(rate):
                return True

        history = self._frame_repository.get_all_history(camera_id)
        if not history:
            return False

        latest_record = history[-1]
        if not latest_record.get("has_pet") or not latest_record.get("position"):
            return False

        rate = movement_rate(latest_record["position"], analysis["position"])
        return is_moving_by_rate(rate)

    async def execute(
        self,
        files: list[Any],
        camera_id: str,
        bowl_x: int | None,
        bowl_y: int | None,
        bowl_width: int | None,
        bowl_height: int | None,
        request_id: str | None = None,
        ezviz_access_token: str | None = None,
    ) -> dict[str, Any]:
        total_uploaded = len(files)
        if total_uploaded == 0:
            raise ValueError("请至少上传一张图片")

        request_id = request_id or str(uuid.uuid4())
        bowl_position = (
            {"x": bowl_x, "y": bowl_y, "width": bowl_width, "height": bowl_height}
            if all([bowl_x, bowl_y, bowl_width, bowl_height])
            else None
        )

        ingested_frames: list[dict[str, Any]] = []
        ingest_errors: list[dict[str, Any]] = []
        for index, file in enumerate(files):
            if not file.content_type or not file.content_type.startswith("image/"):
                ingest_errors.append(
                    {"index": index, "filename": file.filename, "success": False, "error": "文件必须是图片"}
                )
                continue
            image_bytes = await file.read()
            image_timestamp = self._timestamp_extractor.extract(image_bytes) or time.time()
            file_path = self._frame_repository.save_upload(
                camera_id,
                index,
                file.filename or "capture.jpg",
                image_bytes,
            )
            frame_id = self._frame_repository.insert_frame(
                camera_id=camera_id,
                request_id=request_id,
                original_filename=file.filename or "capture.jpg",
                file_path=file_path,
                file_size=len(image_bytes),
                image_timestamp=image_timestamp,
                source="upload",
            )
            self._frame_repository.evict_lru_frames(camera_id)
            frame = self._frame_repository.get_frame_by_id(frame_id)
            if frame:
                ingested_frames.append(frame)

        if not ingested_frames:
            raise RuntimeError("没有可用的图片帧")

        latest_ts = max(frame["image_timestamp"] for frame in ingested_frames)
        candidates = self._frame_repository.get_frames_in_window(camera_id, latest_ts, settings.analysis_window_seconds)
        sampled_candidates, was_sampled = sample_frame_records(candidates, settings.max_sample_frames)
        sampled_ids = {f["id"] for f in sampled_candidates}
        skipped_ids = [f["id"] for f in candidates if f["id"] not in sampled_ids]
        self._frame_repository.mark_frames_status(list(sampled_ids), "sampled")
        self._frame_repository.mark_frames_status(skipped_ids, "skipped")

        analyzed_frames: list[dict[str, Any]] = []
        analyze_errors: list[dict[str, Any]] = []
        for frame in sampled_candidates:
            try:
                self._frame_repository.touch_frames([frame["id"]])
                image_bytes = self._frame_repository.read_file_bytes(frame["file_path"])
                image_for_api = image_bytes
                if len(image_for_api) > settings.max_image_kb_for_api * 1024:
                    image_for_api = compress_image(image_for_api, max_size_kb=settings.max_image_kb_for_api)
                image_base64 = base64.b64encode(image_for_api).decode("utf-8")

                bowl_analysis = analyze_bowl(image_bytes, bowl_position)
                pet_result = self._ezviz.detect_pet_base64(
                    image_base64, access_token=ezviz_access_token
                )
                analysis = parse_pet_detection(pet_result)
                analysis["blue_ratio"] = bowl_analysis["blue_ratio"]
                analysis["food_status"] = bowl_analysis["food_status"]
                analysis["is_in_food_bowl"] = (
                    is_in_food_bowl(analysis["position"], bowl_position)
                    if bowl_position and analysis.get("position")
                    else False
                )

                self._frame_repository.update_frame_detection(frame["id"], analysis)
                frame["analysis"] = analysis
                analyzed_frames.append(frame)
            except Exception as exc:
                analyze_errors.append(
                    {
                        "frame_id": frame["id"],
                        "filename": frame.get("filename"),
                        "success": False,
                        "error": _format_analyze_error(exc),
                    }
                )

        if not analyzed_frames:
            detail = analyze_errors[0]["error"] if analyze_errors else "所有帧分析均失败"
            raise RuntimeError(detail)

        movement_info = compare_frames_movement(analyzed_frames)
        analysis = build_unified_analysis(analyzed_frames, movement_info)
        reference_time = max(f["timestamp"] for f in analyzed_frames)
        if movement_info["total_pairs"] == 0 and analysis.get("has_pet"):
            if self._compare_movement_fallback(analysis, camera_id, reference_time):
                movement_info["is_moving"] = True
                analysis["is_moving"] = True

        self._frame_repository.insert_analysis_record(camera_id, reference_time, analysis)
        analysis = update_pet_state(camera_id, analysis, self._state_repository)

        # 持久化状态变更到后端
        if isinstance(self._state_repository, BackendStateRepository):
            state = self._state_repository.get(camera_id)
            self._state_repository.save_state(camera_id, state)

        pet_frame_count = sum(1 for frame in analyzed_frames if frame["analysis"].get("has_pet"))
        pet_frame_ratio = pet_frame_count / len(analyzed_frames) if analyzed_frames else 0
        activity_score = calculate_activity_score(analysis, movement_info["movement_ratio"], pet_frame_ratio)
        activity_status = get_activity_status(activity_score)
        analysis_result_text = get_analysis_result(analysis)

        return {
            "result": {
                "success": True,
                "has_pet": analysis["has_pet"],
                "is_moving": analysis["is_moving"],
                "is_in_food_bowl": analysis.get("is_in_food_bowl", False),
                "food_status": analysis["food_status"],
                "anomaly": analysis["anomaly"],
                "confidence": round(analysis["confidence"], 4),
                "activity_score": activity_score,
                "activity_status": activity_status,
                "activity_description": get_activity_description(activity_score),
                "analysis_result": analysis_result_text,
                "movement_summary": {
                    "window_seconds": settings.analysis_window_seconds,
                    "total_pairs": movement_info["total_pairs"],
                    "moving_pairs": movement_info["moving_pairs"],
                    "movement_ratio": movement_info["movement_ratio"],
                    "max_movement_rate": movement_info["max_movement_rate"],
                    "avg_movement_rate": movement_info["avg_movement_rate"],
                },
                "reference_timestamp": reference_time,
                "frame_count": len(analyzed_frames),
                "pet_detected_frames": pet_frame_count,
            },
            "summary": {
                "total_uploaded": total_uploaded,
                "ingested_count": len(ingested_frames),
                "ingest_failed_count": len(ingest_errors),
                "candidates_in_window": len(candidates),
                "sampled_count": len(analyzed_frames),
                "analyze_failed_count": len(analyze_errors),
                "sampled": was_sampled,
                "sample_size": settings.max_sample_frames,
                "has_pet": analysis["has_pet"],
                "is_moving": analysis["is_moving"],
                "anomaly": analysis["anomaly"],
            },
        }

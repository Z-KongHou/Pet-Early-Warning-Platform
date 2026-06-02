import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    ezviz_access_token: str = os.getenv(
        "EZVIZ_ACCESS_TOKEN",
        "at.4uqsl8in7pc483xqao8ymm1z1vkpgu8p-64ehzsbtsb-01goxjp-luctlwd8i",
    )
    pet_detection_api: str = "https://open.ys7.com/api/service/intelligence/algo/analysis/pet_detection"
    max_request_size: int = 50 * 1024 * 1024
    max_image_kb_for_api: int = 500
    stationary_threshold: int = 60
    no_eating_threshold: int = 120
    movement_threshold: float = 0.01
    max_history: int = 10
    bowl_empty_blue_ratio: float = 0.85
    max_history_records: int = 3
    max_frames_per_camera: int = 500
    max_sample_frames: int = 20
    analysis_window_seconds: int = 3 * 60
    day_start_hour: int = 8
    day_end_hour: int = 22
    day_stationary_threshold: int = 3 * 60
    night_stationary_threshold: int = 3 * 60
    day_eating_threshold: int = 3 * 60
    night_eating_threshold: int = 3 * 60
    database_path: str = os.getenv("PET_ANALYSIS_DB_PATH", "pet_analysis.db")
    upload_dir_name: str = os.getenv("PET_UPLOAD_DIR", "upload")

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def upload_dir(self) -> Path:
        return self.base_dir / self.upload_dir_name


settings = Settings()

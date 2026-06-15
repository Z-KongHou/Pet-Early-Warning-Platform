"""User preferences and pet profiles backed by SQLite.

Enables personalized RAG answers:
- Preferences: key-value store (experience_level, language_style, concerns, etc.)
- Pet profiles: species, age, sex, medical history per pet
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pet_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    species TEXT,
    age_months INTEGER,
    sex TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class PreferenceRepository:
    """Store and retrieve user preferences and pet profiles."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or (settings.chroma_path / "user_prefs.db")
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.executescript(SCHEMA)

    # ── Preferences ────────────────────────────────────────────

    def get_pref(self, key: str) -> str | None:
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def set_pref(self, key: str, value: str) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO user_preferences (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
                (key, value),
            )

    def get_all_prefs(self) -> dict[str, str]:
        with sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
        return {k: v for k, v in rows}

    def merge_prefs(self, prefs: dict[str, str]) -> None:
        """Merge a dict of preferences (from LLM extraction)."""
        for key, value in prefs.items():
            if key and value:
                self.set_pref(key.strip(), value.strip())
        logger.info("PreferenceRepository: merged %d prefs", len(prefs))

    # ── Pet Profiles ───────────────────────────────────────────

    def get_pets(self) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM pet_profiles ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_pet(self, pet: dict[str, Any]) -> int:
        """Insert or update a pet profile. Returns the pet id."""
        with sqlite3.connect(str(self._db_path)) as conn:
            if pet.get("id"):
                conn.execute(
                    "UPDATE pet_profiles SET name=?, species=?, age_months=?, sex=?, notes=?, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=?",
                    (pet.get("name", ""), pet.get("species"), pet.get("age_months"),
                     pet.get("sex"), pet.get("notes"), pet["id"]),
                )
                return pet["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO pet_profiles (name, species, age_months, sex, notes) VALUES (?, ?, ?, ?, ?)",
                    (pet.get("name", ""), pet.get("species"), pet.get("age_months"),
                     pet.get("sex"), pet.get("notes")),
                )
                return cur.lastrowid or 0

    def delete_pet(self, pet_id: int) -> bool:
        with sqlite3.connect(str(self._db_path)) as conn:
            cur = conn.execute("DELETE FROM pet_profiles WHERE id = ?", (pet_id,))
            return cur.rowcount > 0

    # ── Format for prompt injection ────────────────────────────

    def format_for_prompt(self) -> str:
        """Render user prefs and pet profiles as a compact prompt prefix."""
        pets = self.get_pets()
        prefs = self.get_all_prefs()

        if not pets and not prefs:
            return ""

        lines: list[str] = ["About the user:"]

        if pets:
            for p in pets:
                desc_parts = [p.get("species", "仓鼠")]
                if p.get("age_months"):
                    desc_parts.append(f"{p['age_months']}个月大")
                if p.get("sex"):
                    desc_parts.append({"male": "雄性", "female": "雌性", "公": "雄性", "母": "雌性"}.get(p["sex"].lower(), p["sex"]))
                desc = f"{p['name']}（{'，'.join(desc_parts)}）"
                if p.get("notes"):
                    desc += f" — {p['notes']}"
                lines.append(f"  - {desc}")

        if prefs:
            pref_map = {
                "experience_level": "饲养经验",
                "language_style": "语言偏好",
                "concerns": "关注问题",
            }
            for key, value in prefs.items():
                label = pref_map.get(key, key)
                lines.append(f"  - {label}: {value}")

        return "\n".join(lines)

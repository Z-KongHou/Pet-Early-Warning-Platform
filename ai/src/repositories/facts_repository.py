"""SQLite structured facts table for hamster veterinary knowledge.

Stores disease-symptom-pathogen-drug-dosage relationships extracted
from RAG chunks during ingest. Enables direct SQL lookup for precise
fact queries, bypassing semantic search when exact matches exist.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS hamster_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease TEXT,
    symptom TEXT,
    pathogen TEXT,
    drug TEXT,
    dosage TEXT,
    source_chunk_id TEXT,
    source_file TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_facts_disease ON hamster_facts(disease);
CREATE INDEX IF NOT EXISTS idx_facts_symptom ON hamster_facts(symptom);
CREATE INDEX IF NOT EXISTS idx_facts_drug ON hamster_facts(drug);
CREATE INDEX IF NOT EXISTS idx_facts_pathogen ON hamster_facts(pathogen);
"""


class FactsRepository:
    """CRUD for extracted hamster veterinary facts."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or (settings.chroma_path / "hamster_facts.db")
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.executescript(SCHEMA)

    @property
    def count(self) -> int:
        with sqlite3.connect(str(self._db_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM hamster_facts").fetchone()[0]

    def insert(self, facts: list[dict[str, Any]]) -> int:
        """Insert extracted facts. Each dict may have: disease, symptom, pathogen, drug, dosage, source_chunk_id, source_file, confidence."""
        if not facts:
            return 0
        with sqlite3.connect(str(self._db_path)) as conn:
            rows = [
                (
                    f.get("disease"),
                    f.get("symptom"),
                    f.get("pathogen"),
                    f.get("drug"),
                    f.get("dosage"),
                    f.get("source_chunk_id", ""),
                    f.get("source_file", ""),
                    f.get("confidence", 1.0),
                )
                for f in facts
                if any(f.get(k) for k in ("disease", "symptom", "pathogen", "drug"))
            ]
            conn.executemany(
                "INSERT INTO hamster_facts (disease, symptom, pathogen, drug, dosage, source_chunk_id, source_file, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            logger.info("FactsRepository: inserted %d facts", len(rows))
            return len(rows)

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fuzzy search facts by disease, symptom, drug, or pathogen matching the query."""
        pattern = f"%{query.strip()}%"
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM hamster_facts
                   WHERE disease LIKE ? OR symptom LIKE ? OR drug LIKE ? OR pathogen LIKE ?
                   ORDER BY confidence DESC
                   LIMIT ?""",
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def search_exact(self, disease: str = "", symptom: str = "", drug: str = "", limit: int = 5) -> list[dict[str, Any]]:
        """Exact or LIKE match on specific fields."""
        conditions: list[str] = []
        params: list[str] = []
        if disease:
            conditions.append("disease LIKE ?")
            params.append(f"%{disease}%")
        if symptom:
            conditions.append("symptom LIKE ?")
            params.append(f"%{symptom}%")
        if drug:
            conditions.append("drug LIKE ?")
            params.append(f"%{drug}%")
        if not conditions:
            return []

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM hamster_facts WHERE {' OR '.join(conditions)} ORDER BY confidence DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_by_source(self, source_file: str) -> int:
        with sqlite3.connect(str(self._db_path)) as conn:
            cur = conn.execute("DELETE FROM hamster_facts WHERE source_file = ?", (source_file,))
            return cur.rowcount

    def reset(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM hamster_facts")
        logger.info("FactsRepository: reset all facts")

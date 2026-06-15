"""LLM-based structured fact extraction from RAG chunks.

Runs during ingest to populate the hamster_facts SQLite table.
One LLM call per batch of chunks (not per chunk) to minimize API cost.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """You are a veterinary knowledge extractor for hamster (仓鼠) care.
Extract all disease-symptom-pathogen-drug-dosage relationships from the text below.
For each fact, fill in the fields you can identify. Leave unknown fields as null.
Output ONLY a JSON array of objects. No other text.

Text:
{chunk_text}

Output format (JSON array only):
[
  {{
    "disease": "疾病名称 or null",
    "symptom": "症状 or null",
    "pathogen": "病原体 or null",
    "drug": "药物名称 or null",
    "dosage": "剂量用法 or null",
    "confidence": 0.0-1.0
  }}
]

Rules:
- disease: the medical condition (e.g. "湿尾症", "proliferative ileitis", "wet tail", "脱毛症")
- symptom: observable sign (e.g. "腹泻", "嗜睡", "毛发脱落")
- pathogen: causative organism (e.g. "Lawsonia intracellularis", "蠕形螨")
- drug: medication name (e.g. "四环素", "tetracycline", "恩诺沙星")
- dosage: administration details (e.g. "10mg/kg PO q12h 5-7天")
- confidence: 0.9 if explicitly stated, 0.7 if inferred, 0.5 if uncertain
- If no facts found, output []
"""


class FactExtractor:
    """Extract structured hamster-health facts from documents using LLM."""

    def __init__(self, llm=None) -> None:
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            from clients.llm import get_chat_llm
            self._llm = get_chat_llm()
        return self._llm

    def extract_from_chunks(
        self,
        chunks: list[Document],
        source_file: str = "",
    ) -> list[dict[str, Any]]:
        """Extract facts from a list of chunks. Batches into one LLM call per ~8 chunks."""
        all_facts: list[dict[str, Any]] = []
        batch_size = 8

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            try:
                facts = self._extract_batch(batch)
                for f in facts:
                    f.setdefault("source_file", source_file)
                all_facts.extend(facts)
                logger.info("FactExtractor: batch %d/%d extracted %d facts", i // batch_size + 1, (len(chunks) - 1) // batch_size + 1, len(facts))
            except Exception as exc:
                logger.warning("FactExtractor: batch %d failed: %s", i // batch_size + 1, exc)

        return all_facts

    def _extract_batch(self, chunks: list[Document]) -> list[dict[str, Any]]:
        text = "\n\n---\n\n".join(c.page_content[:600] for c in chunks)
        if len(text) < 50:
            return []

        raw = self.llm.chat(
            "You are a precise JSON extractor. Output only valid JSON, no markdown, no explanation.",
            _EXTRACTION_PROMPT.format(chunk_text=text),
        )
        return self._parse_facts(raw)

    @staticmethod
    def _parse_facts(raw: str) -> list[dict[str, Any]]:
        from utils.parsing import parse_json_array

        parsed = parse_json_array(raw)
        if not parsed:
            return []

        def _normalize(f: dict) -> dict[str, Any]:
            return {
                "disease": str(f["disease"]) if f.get("disease") else None,
                "symptom": str(f["symptom"]) if f.get("symptom") else None,
                "pathogen": str(f["pathogen"]) if f.get("pathogen") else None,
                "drug": str(f["drug"]) if f.get("drug") else None,
                "dosage": str(f["dosage"]) if f.get("dosage") else None,
                "confidence": float(f.get("confidence", 0.9)),
            }

        return [
            _normalize(f)
            for f in parsed
            if isinstance(f, dict) and any(f.get(k) for k in ("disease", "symptom", "pathogen", "drug"))
        ]

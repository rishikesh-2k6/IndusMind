"""Extract industrial entities/relationships from document text via Gemini."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import get_logger
from app.services.entity_extraction.prompts import (
    ENTITY_KINDS,
    ENTITY_SYSTEM,
    RELATIONS,
    build_entity_prompt,
)
from app.services.llm.gemini_client import GeminiClient

logger = get_logger(__name__)

_VALID_KINDS = set(ENTITY_KINDS)
_VALID_RELATIONS = set(RELATIONS)


def normalize_key(value: str) -> str:
    """Canonicalize an entity key for cross-document matching."""
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


@dataclass(slots=True)
class ExtractedGraph:
    entities: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)


class EntityExtractor:
    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    @property
    def enabled(self) -> bool:
        return settings.enable_kg and self._gemini.enabled

    async def extract(self, text: str) -> ExtractedGraph:
        if not self.enabled or not text.strip():
            return ExtractedGraph()
        prompt = build_entity_prompt(text[: settings.kg_extract_max_chars])
        data = await self._gemini.generate_json(prompt, system=ENTITY_SYSTEM)
        return self._normalize(data)

    def _normalize(self, data) -> ExtractedGraph:
        if not isinstance(data, dict):
            return ExtractedGraph()

        entities: list[dict] = []
        seen_entities: set[tuple[str, str]] = set()
        for raw in data.get("entities") or []:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("kind", "")).lower().strip()
            label = str(raw.get("label") or raw.get("key") or "").strip()
            key = normalize_key(str(raw.get("key") or label))
            if kind not in _VALID_KINDS or not key or not label:
                continue
            if (kind, key) in seen_entities:
                continue
            seen_entities.add((kind, key))
            entities.append({
                "kind": kind,
                "key": key,
                "label": label,
                "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else None,
            })

        relations: list[dict] = []
        for raw in data.get("relations") or []:
            if not isinstance(raw, dict):
                continue
            relation = str(raw.get("relation", "")).lower().strip()
            src_kind = str(raw.get("src_kind", "")).lower().strip()
            dst_kind = str(raw.get("dst_kind", "")).lower().strip()
            src_key = normalize_key(str(raw.get("src_key", "")))
            dst_key = normalize_key(str(raw.get("dst_key", "")))
            if relation not in _VALID_RELATIONS or src_kind not in _VALID_KINDS:
                continue
            if dst_kind not in _VALID_KINDS or not src_key or not dst_key:
                continue
            relations.append({
                "src_kind": src_kind, "src_key": src_key,
                "dst_kind": dst_kind, "dst_key": dst_key,
                "relation": relation,
                "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else None,
            })

        logger.info("Entity extraction: %d entities, %d relations", len(entities), len(relations))
        return ExtractedGraph(entities=entities, relations=relations)

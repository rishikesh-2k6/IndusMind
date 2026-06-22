"""Prompts for industrial entity/relationship extraction."""
from __future__ import annotations

ENTITY_SYSTEM = (
    "You are an industrial knowledge-graph extractor. From plant documents "
    "(maintenance, inspection, incident reports, SOPs, manuals) you extract "
    "equipment, failures, maintenance activities, inspections, incidents, people, "
    "locations, and procedures, plus the relationships between them. Extract only "
    "what is stated; never invent equipment tags, dates, or readings."
)

# Valid vocabularies — the model is told to stay within these.
ENTITY_KINDS = (
    "equipment", "failure", "maintenance", "inspection", "incident",
    "person", "location", "procedure",
)
RELATIONS = (
    "has_failure", "underwent_maintenance", "inspected_in", "located_at",
    "operated_by", "connected_to", "references", "mentioned_in",
)


def build_entity_prompt(text: str) -> str:
    kinds = ", ".join(ENTITY_KINDS)
    rels = ", ".join(RELATIONS)
    return (
        "Extract the industrial knowledge graph from the document text below.\n\n"
        f"Entity kinds (use only these): {kinds}\n"
        f"Relation types (use only these): {rels}\n\n"
        "Rules:\n"
        "- For equipment, set key to the tag/ID when present (e.g. P101, B201, C101); "
        "otherwise a short slug of the name.\n"
        "- label is the human-readable name (e.g. 'Pump P101', 'Bearing Wear').\n"
        "- Put dates, readings, results, and summaries into attributes.\n"
        "- Relations connect a source entity to a target entity, e.g. equipment "
        "has_failure failure; equipment underwent_maintenance maintenance; "
        "equipment inspected_in inspection.\n\n"
        "Return ONLY JSON of this exact shape:\n"
        '{"entities":[{"kind":"equipment","key":"P101","label":"Pump P101",'
        '"attributes":{"type":"pump","location":"Unit A"}}],'
        '"relations":[{"src_kind":"equipment","src_key":"P101","dst_kind":"failure",'
        '"dst_key":"bearing_wear","relation":"has_failure",'
        '"attributes":{"date":"2025-03-14","summary":"bearing wear from contamination"}}]}\n\n'
        f"DOCUMENT TEXT:\n{text}"
    )

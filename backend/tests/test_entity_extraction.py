"""Unit tests for entity-extraction normalization and JSON parsing (no network)."""
from app.services.entity_extraction.service import EntityExtractor, normalize_key
from app.services.llm.gemini_client import _parse_json


def test_normalize_key():
    assert normalize_key("P101") == "p101"
    assert normalize_key("Bearing Wear") == "bearing_wear"
    assert normalize_key("  C-101 ") == "c_101"
    assert normalize_key("") == ""


def test_parse_json_plain():
    assert _parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_with_code_fence():
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_garbage_returns_empty():
    assert _parse_json("not json at all") == {}


def test_normalize_filters_invalid_and_dedupes():
    extractor = EntityExtractor.__new__(EntityExtractor)  # no Gemini needed
    data = {
        "entities": [
            {"kind": "equipment", "key": "P101", "label": "Pump P101"},
            {"kind": "equipment", "key": "p101", "label": "Pump P101"},  # dup after normalize
            {"kind": "failure", "key": "Bearing Wear", "label": "Bearing Wear"},
            {"kind": "bogus", "key": "x", "label": "X"},  # invalid kind -> dropped
            {"kind": "equipment", "label": ""},  # no key/label -> dropped
        ],
        "relations": [
            {"src_kind": "equipment", "src_key": "P101", "dst_kind": "failure",
             "dst_key": "Bearing Wear", "relation": "has_failure",
             "attributes": {"date": "2025-03-14"}},
            {"src_kind": "equipment", "src_key": "P101", "dst_kind": "failure",
             "dst_key": "x", "relation": "invented_relation"},  # bad relation -> dropped
        ],
    }
    graph = extractor._normalize(data)
    keys = {(e["kind"], e["key"]) for e in graph.entities}
    assert ("equipment", "p101") in keys
    assert ("failure", "bearing_wear") in keys
    assert len(graph.entities) == 2  # dedup + invalid dropped
    assert len(graph.relations) == 1
    assert graph.relations[0]["dst_key"] == "bearing_wear"


def test_normalize_handles_non_dict():
    extractor = EntityExtractor.__new__(EntityExtractor)
    assert extractor._normalize([]).entities == []
    assert extractor._normalize("nope").relations == []

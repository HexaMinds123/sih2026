import json

import pytest

from knowledge import JsonKnowledgeStore, interaction_key, normalize_medication


def test_normalization_and_order_independence():
    assert normalize_medication("  Warfarin ") == "warfarin"
    assert interaction_key("Warfarin", "Aspirin") == interaction_key("aspirin", "warfarin")


def test_json_store_finds_known_interaction_in_either_order():
    store = JsonKnowledgeStore()
    assert store.find_interaction("Aspirin", "Warfarin") == {
        "severity": "high",
        "warning": "May increase bleeding risk",
    }


def test_json_store_returns_none_for_unknown_interaction():
    assert JsonKnowledgeStore().find_interaction("ibuprofen", "metformin") is None


def test_guideline_lookup_is_case_insensitive():
    assert JsonKnowledgeStore().find_guidance("low_spo2")["parameter"] == "SpO2"


def test_invalid_interaction_data_is_rejected(tmp_path):
    (tmp_path / "drug_interactions.json").write_text(json.dumps({"bad": {}}), encoding="utf-8")
    (tmp_path / "guidelines.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        JsonKnowledgeStore(tmp_path)

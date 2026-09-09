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

def test_prescription_search_filters_by_medication_and_preserves_provenance():
    results = JsonKnowledgeStore().search_guidance(
        "Metformin Type 2 Diabetes 500 mg twice daily clinical guideline",
        metadata_filter={"medication": "metformin", "kind": "prescription_guideline"},
    )

    assert results
    assert all(result["metadata"]["medication"] == "metformin" for result in results)
    assert results[0]["metadata"]["document_id"]
    assert results[0]["metadata"]["section"]


def test_expanded_reference_records_are_available():
    store = JsonKnowledgeStore()
    assert store.find_interaction("apixaban", "ibuprofen")["severity"] == "high"
    assert store.find_guidance("LOW_GLUCOSE")["parameter"] == "Blood Glucose"

def test_unsupported_prescription_medication_has_no_matches():
    assert JsonKnowledgeStore().search_guidance(
        "unknownmedicine clinical guideline",
        metadata_filter={"medication": "unknownmedicine", "kind": "prescription_guideline"},
    ) == []


def test_invalid_interaction_data_is_rejected(tmp_path):
    (tmp_path / "drug_interactions.json").write_text(json.dumps({"bad": {}}), encoding="utf-8")
    (tmp_path / "guidelines.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        JsonKnowledgeStore(tmp_path)

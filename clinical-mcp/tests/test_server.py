import pytest

import server


def setup_function():
    server._store = None


def test_query_known_interaction():
    result = server.query_drug_interactions(["Warfarin", "Aspirin"])
    assert result["interaction_found"] is True
    assert result["interactions"][0]["severity"] == "high"


def test_query_requires_two_distinct_medications():
    with pytest.raises(ValueError):
        server.query_drug_interactions(["warfarin"])
    with pytest.raises(ValueError):
        server.query_drug_interactions(["warfarin", "Warfarin"])


def test_unknown_guidance_is_structured():
    result = server.search_clinical_guidance("not_known")
    assert result == {
        "found": False,
        "anomaly_code": "NOT_KNOWN",
        "message": "No curated guidance was found for this observation code.",
    }


def test_guidance_is_observation_based():
    result = server.search_clinical_guidance("LOW_SPO2")
    assert result["found"] is True
    assert "diagnosis" in result["note"].lower()
    assert "definitely" not in str(result).lower()

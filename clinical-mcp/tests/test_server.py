import os

import pytest

import server


def setup_function():
    os.environ["CLINICAL_MCP_STORAGE"] = "json"
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
    assert result["found"] is False
    assert result["anomaly_code"] == "NOT_KNOWN"
    assert result["evidence"] == []


def test_guidance_is_observation_based():
    result = server.search_clinical_guidance("LOW_SPO2")
    assert result["found"] is True
    assert "diagnosis" in result["note"].lower()
    assert "definitely" not in str(result).lower()


def test_search_prescription_guidance_reuses_existing_retrieval():
    class FakeStore:
        def search_guidance(self, query, limit=5, metadata_filter=None):
            assert query == "Metformin Type 2 Diabetes 500 mg twice daily clinical guideline"
            assert limit == 5
            assert metadata_filter == {"medication": "metformin", "kind": "prescription_guideline"}
            return [{
                "text": "Reference evidence",
                "score": 0.91,
                "source": "guideline.pdf",
                "metadata": {"document_id": "doc-1", "section": "Dosing", "page": 4},
            }]

    server._store = FakeStore()
    result = server.search_prescription_guidance(
        "Metformin", "Type 2 Diabetes", "500 mg twice daily"
    )

    assert result["medication"] == "metformin"
    assert result["evidence_found"] is True
    assert result["human_review_required"] is True
    assert result["reason"] is None
    assert result["evidence"] == [{
        "text": "Reference evidence",
        "source": "guideline.pdf",
        "document_id": "doc-1",
        "section": "Dosing",
        "page": 4,
        "version": None,
        "jurisdiction": None,
        "publication_date": None,
        "topic": None,
        "source_url": None,
        "similarity_score": 0.91,
    }]


def test_search_prescription_guidance_rejects_blank_optional_fields():
    with pytest.raises(ValueError):
        server.search_prescription_guidance("Metformin", condition=" ")


def test_prescription_guidance_filters_unsupported_and_supports_amlodipine():
    unsupported = server.search_prescription_guidance("Unknownmedicine", "Unknown condition")
    assert unsupported["evidence_found"] is False
    assert unsupported["evidence"] == []
    assert unsupported["reason"] == "No sufficiently relevant clinical evidence found."

    amlodipine = server.search_prescription_guidance("Amlodipine", "Hypertension", "5 mg once daily")
    assert amlodipine["evidence_found"] is True
    assert all(item["source"] == "DailyMed" for item in amlodipine["evidence"])
    assert all(item["document_id"] for item in amlodipine["evidence"])

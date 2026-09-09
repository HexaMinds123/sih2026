"""Automated test suite for Patient EHR MCP Server and RAG integration."""

import os
import pytest
from database import PatientDatabase
import server
import rag


TOKEN = "medical-agent-secret-token"
WRONG_TOKEN = "invalid-secret-token"


@pytest.fixture(autouse=True)
def init_test_db():
    """Ensure database has demo records."""
    db = PatientDatabase("patients.db")
    if not db.patient_exists("P001"):
        import seed_data
        seed_data.seed_demo_patients()
    return db


def test_resource_patient_profile_success():
    """Test reading patient://profile/P001 returns correct demographics, allergies, conditions."""
    profile = server.patient_profile("P001")
    assert profile["patient_id"] == "P001"
    assert profile["name"] == "John Doe"
    assert profile["age"] == 52
    assert "Penicillin" in profile["allergies"]
    assert "Type 2 Diabetes" in profile["conditions"] or "Hypertension" in profile["conditions"]


def test_resource_patient_profile_not_found():
    """Test reading a non-existent patient resource returns PATIENT_NOT_FOUND error."""
    result = server.patient_profile("P999")
    assert result["code"] == "PATIENT_NOT_FOUND"
    assert result["error"] is True


def test_fetch_active_prescriptions_authorized():
    """Test fetching active prescriptions with a valid token."""
    res = server.fetch_active_prescriptions("P001", TOKEN)
    assert res["patient_id"] == "P001"
    drugs = [rx["drug"] for rx in res["prescriptions"]]
    assert "Metformin" in drugs
    assert "Amlodipine" in drugs


def test_fetch_active_prescriptions_unauthorized():
    """Test calling tool with an invalid token returns UNAUTHORIZED."""
    res = server.fetch_active_prescriptions("P001", WRONG_TOKEN)
    assert res["code"] == "UNAUTHORIZED"
    assert res["error"] is True


def test_fetch_active_prescriptions_patient_not_found():
    """Test calling tool with unknown patient ID returns PATIENT_NOT_FOUND."""
    res = server.fetch_active_prescriptions("P999", TOKEN)
    assert res["code"] == "PATIENT_NOT_FOUND"
    assert res["error"] is True


def test_get_allergies():
    """Test get_allergies tool."""
    res = server.get_allergies("P001", TOKEN)
    assert res["patient_id"] == "P001"
    assert "Penicillin" in res["allergies"]

    # Unauthorized check
    unauth = server.get_allergies("P001", WRONG_TOKEN)
    assert unauth["code"] == "UNAUTHORIZED"


def test_get_medical_conditions():
    """Test get_medical_conditions tool."""
    res = server.get_medical_conditions("P002", TOKEN)
    assert res["patient_id"] == "P002"
    assert "Asthma" in res["conditions"]

    # Unauthorized check
    unauth = server.get_medical_conditions("P002", WRONG_TOKEN)
    assert unauth["code"] == "UNAUTHORIZED"


def test_get_emergency_contact():
    """Test get_emergency_contact tool."""
    res = server.get_emergency_contact("P001", TOKEN)
    assert res["patient_id"] == "P001"
    assert res["emergency_contact"]["name"] == "Jane Doe"
    assert res["emergency_contact"]["relationship"] == "Spouse"

    # Unauthorized check
    unauth = server.get_emergency_contact("P001", WRONG_TOKEN)
    assert unauth["code"] == "UNAUTHORIZED"


def test_search_patient_context_rag():
    """Test RAG semantic search across patient EHR narratives."""
    res = server.search_patient_context("patient with diabetes and hypertension taking metformin", TOKEN)
    assert res["count"] > 0
    top_match = res["results"][0]
    assert top_match["patient_id"] == "P001"
    assert "John Doe" in top_match["text"]
    assert top_match["score"] >= 0.25


def test_unified_search_rag():
    """Test unified RAG search across both EHR and Clinical guideline stores."""
    # 1. Search patients scope
    p_res = server.unified_search("asthma respiratory wheezing", TOKEN, search_scope="patients")
    assert len(p_res["results"]) > 0
    assert p_res["results"][0]["source"] == "patient"

    # 2. Search both scope
    both_res = server.unified_search("low oxygen saturation hypoxemia", TOKEN, search_scope="both")
    assert len(both_res["results"]) > 0
    sources = [r["source"] for r in both_res["results"]]
    assert "clinical" in sources or "patient" in sources


def test_check_patient_drug_safety_cross_server():
    """Test cross-server safety tool: detects Warfarin + Aspirin interaction on P003."""
    res = server.check_patient_drug_safety("P003", TOKEN)
    assert res["patient_id"] == "P003"
    assert res["interaction_found"] is True
    assert len(res["interactions"]) > 0
    # Check severity and warning
    interaction = res["interactions"][0]
    assert "Warfarin" in interaction["drugs"]
    assert "Aspirin" in interaction["drugs"]
    assert interaction["severity"] == "high"


if __name__ == "__main__":
    pytest.main(["-v", __file__])

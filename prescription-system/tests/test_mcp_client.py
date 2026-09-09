import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import _extractions, app
from app.mcp_client import ClinicalMCPClient, ClinicalMCPError
from app.models import ExtractionResponse, Medication, OCRResult, Patient, Prescription


CLINICAL_MCP_PATH = Path(__file__).resolve().parents[2] / "clinical-mcp"


def run(coroutine):
    return asyncio.run(coroutine)


def test_missing_mcp_path_is_handled():
    async def scenario():
        client = ClinicalMCPClient(server_path=Path("does-not-exist"))
        with pytest.raises(ClinicalMCPError, match="directory not found"):
            await client.connect()

    run(scenario())


def test_stdio_handshake_tool_listing_and_calls():
    environment = os.environ.copy()
    environment["CLINICAL_MCP_STORAGE"] = "json"

    async def scenario():
        client = ClinicalMCPClient(server_path=CLINICAL_MCP_PATH, environment=environment)
        try:
            tools = await client.connect()
            assert {
                "query_drug_interactions",
                "search_clinical_guidance",
                "search_prescription_guidance",
            }.issubset(tools)

            interactions = await client.query_drug_interactions(["Warfarin", "Aspirin"])
            guidance = await client.search_prescription_guidance(
                "Metformin", "Type 2 Diabetes", "500 mg twice daily"
            )
            return interactions, guidance
        finally:
            await client.close()

    interactions, guidance = run(scenario())
    assert interactions["interaction_found"] is True
    assert interactions["interactions"][0]["severity"] == "high"
    assert guidance["medication"] == "metformin"
    assert "evidence_found" in guidance
    assert "human_review_required" in guidance


def test_mcp_check_endpoint_returns_graceful_failure(monkeypatch):
    prescription_id = "RX-MCP-FAILURE"
    _extractions[prescription_id] = ExtractionResponse(
        prescription_id=prescription_id,
        ocr=OCRResult(raw_text="Metformin 500 mg", ocr_confidence=0.9),
        prescription=Prescription(
            patient=Patient(),
            medications=[Medication(name="Metformin", strength="500 mg")],
        ),
        human_verification_required=False,
    )

    class FailingClient:
        async def connect(self):
            raise ClinicalMCPError("Clinical MCP server unavailable")

        async def close(self):
            return None

    monkeypatch.setattr("app.main.ClinicalMCPClient", FailingClient)
    response = TestClient(app).post(f"/prescription/{prescription_id}/mcp-check")

    assert response.status_code == 200
    assert response.json()["mcp"] == {
        "connected": False,
        "error": "Clinical MCP server unavailable",
        "human_review_required": True,
    }
    _extractions.pop(prescription_id, None)


def test_mcp_check_endpoint_returns_remote_results(monkeypatch):
    prescription_id = "RX-MCP-SUCCESS"
    _extractions[prescription_id] = ExtractionResponse(
        prescription_id=prescription_id,
        ocr=OCRResult(raw_text="Metformin and Aspirin", ocr_confidence=0.9),
        prescription=Prescription(
            patient=Patient(),
            condition="Type 2 Diabetes",
            medications=[
                Medication(name="Metformin", strength="500 mg", frequency="twice daily"),
                Medication(name="Aspirin", strength="75 mg", frequency="once daily"),
            ],
        ),
        human_verification_required=False,
    )

    class SuccessfulClient:
        async def connect(self):
            return [
                "query_drug_interactions",
                "search_clinical_guidance",
                "search_prescription_guidance",
            ]

        async def query_drug_interactions(self, medications):
            return {"interaction_found": True, "drugs": medications, "interactions": []}

        async def search_prescription_guidance(self, medication, condition=None, dosage=None):
            return {
                "medication": medication.lower(),
                "condition": condition,
                "dosage": dosage,
                "evidence_found": False,
                "evidence": [],
                "human_review_required": True,
            }

        async def close(self):
            return None

    monkeypatch.setattr("app.main.ClinicalMCPClient", SuccessfulClient)
    response = TestClient(app).post(f"/prescription/{prescription_id}/mcp-check")

    assert response.status_code == 200
    body = response.json()
    assert body["mcp"]["connected"] is True
    assert len(body["mcp"]["guideline_evidence"]) == 2
    assert body["mcp"]["drug_interactions"]["interaction_found"] is True
    _extractions.pop(prescription_id, None)

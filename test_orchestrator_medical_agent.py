"""
Test Suite: Healthcare AI Orchestrator x Medical & Pharmaceutical Agent Integration

Tests the HealthcareOrchestrator.evaluate_prescription() method introduced in Phase 7.
All tests use FakeMedicalAgentAdapter -- no real MCP subprocess is spawned.

Test inventory:
  test_01 -- invocation_and_schema
  test_02 -- critical_escalation_propagation
  test_03 -- human_review_gate_across_all_statuses  (parametrized x 4)
  test_04 -- insufficient_information_propagation
  test_05 -- graceful_error_handling
  test_06 -- regression_existing_workflows
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path setup -- ensure orchestrator and prescription-system are importable.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RX_ROOT = ROOT / "prescription-system"
if str(RX_ROOT) not in sys.path:
    sys.path.insert(0, str(RX_ROOT))

from orchestrator import HealthcareOrchestrator, MedicalAgentAdapter  # noqa: E402

from app.models import (  # noqa: E402
    AnalysisResponse,
    ExtractionResponse,
    Medication,
    MedicationAnalysis,
    OCRResult,
    Patient,
    Prescription,
)


# ---------------------------------------------------------------------------
# FakeMedicalAgentAdapter
# ---------------------------------------------------------------------------

class FakeMedicalAgentAdapter:
    """
    Synchronous drop-in replacement for MedicalAgentAdapter in tests.
    Returns a pre-built AnalysisResponse (or degradation dict) without spawning
    any subprocess or async event loop.
    """

    def __init__(self, response: Any, available: bool = True) -> None:
        self.available = available
        self._response = response

    def run(self, extraction: Any = None, **kwargs) -> Any:
        return self._response


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_extraction(
    *medications: Medication,
    prescription_id: str = "RX-TEST",
    condition: str | None = "Type 2 Diabetes",
    ocr_review: bool = False,
) -> ExtractionResponse:
    """Build a minimal but valid ExtractionResponse."""
    return ExtractionResponse(
        prescription_id=prescription_id,
        ocr=OCRResult(
            raw_text="prescription text",
            ocr_confidence=0.95,
            human_verification_required=ocr_review,
        ),
        prescription=Prescription(
            patient=Patient(name="Test Patient", age=45),
            condition=condition,
            medications=list(medications),
        ),
        human_verification_required=ocr_review,
    )


def _make_analysis(
    status: str,
    prescription_id: str = "RX-TEST",
    issues: list[str] | None = None,
    interactions: dict | None = None,
    medications: list[MedicationAnalysis] | None = None,
) -> AnalysisResponse:
    """Build a minimal AnalysisResponse for the given status."""
    return AnalysisResponse(
        prescription_id=prescription_id,
        status=status,
        human_review_required=(status != "INFORMATIONAL"),
        medications=medications or [],
        drug_interactions=interactions or {"interaction_found": False, "interactions": []},
        issues=issues or [],
        audit={"tools_called": []},
    )


def _make_orchestrator(fake_adapter: FakeMedicalAgentAdapter) -> HealthcareOrchestrator:
    """Return a HealthcareOrchestrator with medical_agent swapped for the fake."""
    o = HealthcareOrchestrator()
    o.medical_agent = fake_adapter
    return o


# ---------------------------------------------------------------------------
# Required keys in every evaluate_prescription() result.
# ---------------------------------------------------------------------------
REQUIRED_KEYS = {
    "patient_id",
    "prescription_id",
    "risk_level",
    "status",
    "approved",
    "human_review_required",
    "medical_analysis",
    "issues",
    "drug_interactions",
    "event_id",
}


# ===========================================================================
# test_01 -- Invocation and schema
# ===========================================================================

def test_01_invocation_and_schema():
    """
    evaluate_prescription() returns a dict with all required schema keys
    when the Medical Agent returns INFORMATIONAL.
    """
    fake = FakeMedicalAgentAdapter(
        _make_analysis(
            status="INFORMATIONAL",
            prescription_id="RX-001",
            medications=[
                MedicationAnalysis(
                    medication="Metformin",
                    condition="Type 2 Diabetes",
                    dosage="500 mg twice daily",
                    evidence_status="EVIDENCE_FOUND",
                )
            ],
        )
    )
    orchestrator = _make_orchestrator(fake)
    extraction = _make_extraction(
        Medication(name="Metformin", strength="500 mg", frequency="twice daily"),
        prescription_id="RX-001",
    )

    result = orchestrator.evaluate_prescription(extraction)

    assert REQUIRED_KEYS.issubset(result.keys()), (
        f"Missing keys: {REQUIRED_KEYS - result.keys()}"
    )
    assert result["risk_level"] == "MODERATE"
    assert result["status"] == "PENDING_CONFIRMATION"
    assert result["approved"] is False
    assert result["human_review_required"] is True
    assert result["medical_analysis"]["prescription_id"] == "RX-001"
    # INFORMATIONAL => no audit event needed
    assert result["event_id"] is None


# ===========================================================================
# test_02 -- Critical escalation propagation
# ===========================================================================

def test_02_critical_escalation_propagation():
    """
    CRITICAL_REVIEW_REQUIRED -> risk_level=CRITICAL and audit event logged.
    """
    high_severity_interaction = {
        "interaction_found": True,
        "drugs": ["Warfarin", "Aspirin"],
        "interactions": [
            {"severity": "high", "warning": "Concurrent use increases bleeding risk."}
        ],
    }
    fake = FakeMedicalAgentAdapter(
        _make_analysis(
            status="CRITICAL_REVIEW_REQUIRED",
            prescription_id="RX-WARF",
            issues=["High-severity drug interaction: Warfarin + Aspirin"],
            interactions=high_severity_interaction,
        )
    )
    orchestrator = _make_orchestrator(fake)
    extraction = _make_extraction(
        Medication(name="Warfarin", strength="2 mg", frequency="daily"),
        Medication(name="Aspirin", strength="75 mg", frequency="daily"),
        prescription_id="RX-WARF",
    )

    result = orchestrator.evaluate_prescription(extraction)

    assert result["risk_level"] == "CRITICAL"
    assert result["status"] == "PENDING_CONFIRMATION"
    assert result["approved"] is False
    assert result["human_review_required"] is True
    assert result["event_id"] is not None
    assert result["event_id"].startswith("EVENT-")
    assert result["drug_interactions"]["interaction_found"] is True


# ===========================================================================
# test_03 -- Human review gate across all statuses (parametrized)
# ===========================================================================

@pytest.mark.parametrize("status", [
    "CRITICAL_REVIEW_REQUIRED",
    "REVIEW_REQUIRED",
    "INSUFFICIENT_INFORMATION",
    "INFORMATIONAL",
])
def test_03_human_review_gate_across_all_statuses(status: str):
    """
    human_review_required=True and approved=False for every Medical Agent status.
    No status ever auto-approves a prescription.
    """
    fake = FakeMedicalAgentAdapter(
        _make_analysis(status=status, prescription_id="RX-GATE")
    )
    orchestrator = _make_orchestrator(fake)
    extraction = _make_extraction(
        Medication(name="Lisinopril", strength="10 mg", frequency="once daily"),
        prescription_id="RX-GATE",
    )

    result = orchestrator.evaluate_prescription(extraction)

    assert result["human_review_required"] is True, (
        f"human_review_required must be True for status={status}"
    )
    assert result["approved"] is False, (
        f"approved must be False for status={status}"
    )
    assert result["status"] == "PENDING_CONFIRMATION"


# ===========================================================================
# test_04 -- Insufficient information propagation
# ===========================================================================

def test_04_insufficient_information_propagation():
    """
    INSUFFICIENT_INFORMATION -> risk_level=HIGH (not downgraded); issues propagated.
    """
    issues = [
        "Prescription condition is missing",
        "Dosage is missing for Amoxicillin",
        "Frequency is missing for Amoxicillin",
    ]
    fake = FakeMedicalAgentAdapter(
        _make_analysis(
            status="INSUFFICIENT_INFORMATION",
            prescription_id="RX-INCOMPLETE",
            issues=issues,
        )
    )
    orchestrator = _make_orchestrator(fake)
    extraction = _make_extraction(
        Medication(name="Amoxicillin"),
        prescription_id="RX-INCOMPLETE",
        condition=None,
    )

    result = orchestrator.evaluate_prescription(extraction)

    assert result["risk_level"] == "HIGH", (
        "INSUFFICIENT_INFORMATION must map to HIGH, not be downgraded"
    )
    assert result["issues"] == issues
    assert result["approved"] is False
    assert result["human_review_required"] is True
    # HIGH risk => audit logged
    assert result["event_id"] is not None


# ===========================================================================
# test_05 -- Graceful error handling
# ===========================================================================

def test_05_graceful_error_handling():
    """
    When adapter.run() raises, evaluate_prescription() does NOT propagate;
    returns structured degradation in medical_analysis.
    """

    class ExplodingAdapter:
        available = True

        def run(self, extraction: Any = None, **kwargs) -> Any:
            raise RuntimeError("Simulated Medical Agent crash")

    orchestrator = _make_orchestrator(ExplodingAdapter())  # type: ignore[arg-type]
    extraction = _make_extraction(
        Medication(name="Metformin", strength="500 mg", frequency="twice daily"),
    )

    # Must not raise
    result = orchestrator.evaluate_prescription(extraction)

    assert result["medical_analysis"]["available"] is False
    assert result["medical_analysis"]["human_review_required"] is True
    assert result["human_review_required"] is True
    assert result["approved"] is False
    assert result["status"] == "PENDING_CONFIRMATION"


# ===========================================================================
# test_06 -- Regression: existing orchestrator workflows unchanged
# ===========================================================================

def test_06_regression_existing_workflows():
    """
    Phase 7 must not break process_telemetry (normal vitals -> STABLE, no EHR call),
    doctor_decision with invalid action, or the MedicalAgentAdapter wiring.
    """
    orchestrator = HealthcareOrchestrator()

    # Normal vitals -> STABLE (no EHR call, avoids MongoDB issue)
    assert callable(orchestrator.process_telemetry)
    telem_result = orchestrator.process_telemetry("P-REGRESSION", {
        "heart_rate": 72, "spo2": 98, "systolic_bp": 120, "diastolic_bp": 80,
    })
    assert telem_result["risk_level"] == "NORMAL"
    assert telem_result["status"] == "STABLE"
    assert telem_result["anomalies"] == []

    # Invalid action -> error dict (no EHR needed)
    decision = orchestrator.doctor_decision(
        event_id="EVENT-FAKE",
        action="INVALID_ACTION",
        doctor_name="Dr. Regression Test",
    )
    assert decision["success"] is False
    assert "error" in decision
    assert "INVALID_ACTION" in decision["error"]

    # MedicalAgentAdapter is wired
    assert hasattr(orchestrator, "medical_agent")
    assert isinstance(orchestrator.medical_agent, MedicalAgentAdapter)

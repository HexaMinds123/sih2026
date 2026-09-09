"""
Test Suite for Healthcare AI Orchestrator Agent (orchestrator.py)

Tests the coordinated tri-server workflow:
1. Normal vitals detection (no escalation)
2. Low SpO2 + Tachycardia anomaly evaluation (EHR + Clinical + Notification)
3. Clinician CONFIRM workflow (Token minting -> SMS Dispatch)
4. Clinician REJECT workflow (Rejection audit trail)
5. Multi-factor drug interaction escalation (Marcus Vance P003)
"""

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator import HealthcareOrchestrator


@pytest.fixture
def orchestrator():
    return HealthcareOrchestrator()


def test_01_normal_vitals_no_escalation(orchestrator):
    """Verify that normal vital parameters return STABLE without triggering an escalation."""
    vitals = {
        "heart_rate": 72,
        "spo2": 98,
        "systolic_bp": 120,
        "diastolic_bp": 80
    }
    result = orchestrator.process_telemetry("P001", vitals)
    assert result["risk_level"] == "NORMAL"
    assert result["status"] == "STABLE"
    assert len(result["anomalies"]) == 0


def test_02_critical_telemetry_triggers_full_orchestration(orchestrator):
    """Verify that SpO2 drop triggers EHR context retrieval, clinical guidance, and audit logging."""
    vitals = {
        "heart_rate": 125,
        "spo2": 87,
        "systolic_bp": 138,
        "diastolic_bp": 88
    }
    result = orchestrator.process_telemetry("P001", vitals)

    assert result["risk_level"] == "CRITICAL"
    assert result["status"] == "PENDING_CONFIRMATION"
    assert result["requires_human_confirmation"] is True
    assert result["event_id"].startswith("EVENT-")

    # Verify EHR context
    context = result["patient_context"]
    assert "Type 2 Diabetes" in context["conditions"]
    assert "Hypertension" in context["conditions"]
    assert "Metformin" in context["active_prescriptions"]

    # Verify Clinical guidelines
    guide_codes = [g["code"] for g in result["clinical_guidelines"]]
    assert "LOW_SPO2" in guide_codes
    assert "HIGH_HR" in guide_codes


def test_03_clinician_confirm_action(orchestrator):
    """Verify that a doctor confirming an escalation dispatches SMS and records DISPATCHED."""
    vitals = {"heart_rate": 130, "spo2": 86}
    eval_result = orchestrator.process_telemetry("P001", vitals)
    event_id = eval_result["event_id"]
    contact_phone = eval_result["patient_context"]["emergency_contact"]["phone"]

    # Doctor CONFIRMS
    decision = orchestrator.doctor_decision(
        event_id=event_id,
        action="CONFIRM",
        doctor_name="Dr. Gregory House, MD",
        phone=contact_phone
    )

    assert decision["success"] is True
    assert decision["action"] == "CONFIRM"
    assert decision["status"] == "DISPATCHED"
    assert decision["dispatch_id"].startswith("MOCK-SMS-")
    assert decision["phone"] == contact_phone


def test_04_clinician_reject_action(orchestrator):
    """Verify that a doctor rejecting an escalation updates audit trail to REJECTED."""
    vitals = {"heart_rate": 115, "spo2": 89}
    eval_result = orchestrator.process_telemetry("P002", vitals)
    event_id = eval_result["event_id"]

    # Doctor REJECTS
    decision = orchestrator.doctor_decision(
        event_id=event_id,
        action="REJECT",
        doctor_name="Dr. Allison Cameron, MD",
        reason="Sensor artifact - finger probe was dislodged during ambulation."
    )

    assert decision["success"] is True
    assert decision["action"] == "REJECT"
    assert decision["status"] == "REJECTED"
    assert decision["rejected_by"] == "Dr. Allison Cameron, MD"


def test_05_cardiac_polypharmacy_interaction_alert(orchestrator):
    """Verify that Marcus Vance (P003) triggers drug interaction alerts when telemetry is evaluated."""
    vitals = {"heart_rate": 105, "spo2": 94}
    eval_result = orchestrator.process_telemetry("P003", vitals)

    # Active meds include Warfarin and Aspirin
    assert len(eval_result["drug_interactions"]) > 0
    first_warn = eval_result["drug_interactions"][0]
    assert "Warfarin" in first_warn["drugs"] or "warfarin" in first_warn["drugs"]
    assert eval_result["risk_level"] in ("CRITICAL", "HIGH")

"""
Test Suite for Notification MCP Server (notification-mcp)

Validates:
1. Audit trail logging creates PENDING_CONFIRMATION events
2. Direct SMS dispatch without token is blocked (human confirmation invariant)
3. Clinician confirmation mints phone-bound, 5-minute expiry single-use token
4. Replay attacks are rejected (tokens cannot be reused)
5. Phone tampering is rejected (PHONE_MISMATCH when caller tries different phone)
6. Expired tokens are rejected (TOKEN_EXPIRED)
7. Successful SMS dispatch records DISPATCHED status in audit trail
8. Forced SMS carrier failures transition to FAILED with full error audit
9. State transition guards: cannot confirm/reject non-PENDING events (INVALID_STATE_TRANSITION)
10. Idempotency guards prevent duplicate SMS dispatches on retries
"""

import sys
from pathlib import Path
import pytest

# Ensure notification-mcp is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import database
from notifications import get_mock_sender
import server


@pytest.fixture(autouse=True)
def clean_test_db(tmp_path, monkeypatch):
    """Use an isolated temporary SQLite database for each test."""
    test_db = tmp_path / "test_audit.db"
    monkeypatch.setenv("NOTIFICATION_DB_PATH", str(test_db))
    database.init_db(test_db)
    mock = get_mock_sender()
    mock.set_force_failure(False)
    mock.sent_messages.clear()
    return test_db


def test_01_log_audit_trail():
    """Verify that logging an event records PENDING_CONFIRMATION in audit_logs."""
    event = server.log_audit_trail(
        patient_id="P001",
        event_type="MEDICATION_SAFETY_ALERT",
        risk_level="CRITICAL",
        message="Severe interaction between Warfarin and Aspirin detected.",
        phone="+15551234567"
    )

    assert event["event_id"].startswith("EVENT-")
    assert event["status"] == "PENDING_CONFIRMATION"
    assert event["requires_human_confirmation"] is True
    assert event["patient_id"] == "P001"
    assert event["phone"] == "+15551234567"

    # Verify retrieval from audit trail
    trail = server.get_audit_trail(event["event_id"])
    assert trail["status"] == "success"
    assert trail["audit_event"]["status"] == "PENDING_CONFIRMATION"


def test_02_direct_sms_without_token_is_blocked():
    """Verify that autonomous SMS trigger without valid token is strictly blocked."""
    # Attempt with empty token
    result = server.trigger_emergency_sms(
        patient_id="P001",
        phone="+15551234567",
        message="Immediate ER visit required!",
        confirmation_token=""
    )
    assert result["success"] is False
    assert result["status"] in ("error", "PENDING_CONFIRMATION")
    assert result["error_code"] == "MISSING_TOKEN"
    assert result["requires_human_confirmation"] is True

    # Attempt with bogus token
    result_bogus = server.trigger_emergency_sms(
        patient_id="P001",
        phone="+15551234567",
        message="Immediate ER visit required!",
        confirmation_token="tok_fake_token_12345"
    )
    assert result_bogus["success"] is False
    assert result_bogus["status"] in ("error", "PENDING_CONFIRMATION")
    assert result_bogus["error_code"] == "INVALID_TOKEN"
    assert result_bogus["requires_human_confirmation"] is True

    # Confirm no SMS was sent
    mock = get_mock_sender()
    assert len(mock.sent_messages) == 0


def test_03_confirm_escalation_mints_token_and_binds_phone():
    """Verify clinician confirmation generates 5-minute single-use phone-bound token."""
    event = server.log_audit_trail(
        patient_id="P002",
        event_type="HYPERTENSIVE_CRISIS",
        risk_level="CRITICAL",
        message="BP 190/115 mmHg.",
        phone="+15559876543"
    )
    event_id = event["event_id"]

    confirmation = server.confirm_escalation(
        event_id=event_id,
        confirmed_by="Dr. Sarah Connor, MD"
    )

    assert confirmation["status"] == "CONFIRMED"
    assert confirmation["event_id"] == event_id
    assert confirmation["bound_phone"] == "+15559876543"
    assert confirmation["confirmation_token"].startswith("tok_")
    assert confirmation["validity_seconds"] == 300
    assert "expires_at" in confirmation

    # Audit log should be updated to CONFIRMED
    trail = server.get_audit_trail(event_id)
    assert trail["audit_event"]["status"] == "CONFIRMED"
    assert trail["audit_event"]["confirmed_by"] == "Dr. Sarah Connor, MD"


def test_04_token_phone_binding_prevents_phone_tampering():
    """Verify that replay of token with a different phone number is rejected with PHONE_MISMATCH."""
    event = server.log_audit_trail(
        patient_id="P001",
        event_type="ALLERGY_ALERT",
        risk_level="HIGH",
        message="Severe Penicillin allergy alert.",
        phone="+15551112222"
    )
    event_id = event["event_id"]

    confirmation = server.confirm_escalation(
        event_id=event_id,
        confirmed_by="Dr. Gregory House, MD"
    )
    token = confirmation["confirmation_token"]

    # Tampered dispatch attempt to an attacker-controlled or different number
    tampered_result = server.trigger_emergency_sms(
        patient_id="P001",
        phone="+15559998888",  # Different number!
        message="Fake emergency alert redirect",
        confirmation_token=token
    )

    assert tampered_result["success"] is False
    assert tampered_result["status"] in ("error", "PENDING_CONFIRMATION")
    assert tampered_result["error_code"] == "PHONE_MISMATCH"
    assert "strictly bound to phone '+15551112222'" in tampered_result["message"]
    assert tampered_result["requires_human_confirmation"] is True

    # Mock sender should NOT have sent any message
    mock = get_mock_sender()
    assert len(mock.sent_messages) == 0


def test_05_token_expiry_guard():
    """Verify that expired tokens cannot be used to dispatch SMS."""
    event = server.log_audit_trail(
        patient_id="P003",
        event_type="SYNCOPE_EPISODE",
        risk_level="HIGH",
        message="Patient collapsed at home.",
        phone="+15553334444"
    )
    event_id = event["event_id"]

    # Confirm with explicit negative expiry (-10 seconds)
    success, conf = database.confirm_event(
        event_id=event_id,
        confirmed_by="Dr. Who, MD",
        expiry_seconds=-10
    )
    assert success is True
    expired_token = conf["confirmation_token"]

    result = server.trigger_emergency_sms(
        patient_id="P003",
        phone="+15553334444",
        message="Emergency notice",
        confirmation_token=expired_token
    )

    assert result["success"] is False
    assert result["status"] in ("error", "PENDING_CONFIRMATION")
    assert result["error_code"] == "TOKEN_EXPIRED"
    assert result["requires_human_confirmation"] is True


def test_06_single_use_token_replay_attack_prevention():
    """Verify that once a token is used, subsequent attempts with that token fail."""
    event = server.log_audit_trail(
        patient_id="P004",
        event_type="CHEST_PAIN",
        risk_level="CRITICAL",
        message="Acute sub-sternal chest pain radiating to left arm.",
        phone="+15554445555"
    )
    event_id = event["event_id"]

    confirmation = server.confirm_escalation(
        event_id=event_id,
        confirmed_by="Dr. Leonard McCoy, MD"
    )
    token = confirmation["confirmation_token"]

    # First dispatch -> SUCCESS
    res1 = server.trigger_emergency_sms(
        patient_id="P004",
        phone="+15554445555",
        message="Urgent: Transporting to cardiac unit.",
        confirmation_token=token
    )
    assert res1["status"] == "DISPATCHED"

    # Second dispatch with SAME token -> BLOCKED
    res2 = server.trigger_emergency_sms(
        patient_id="P004",
        phone="+15554445555",
        message="Duplicate urgent dispatch attempt.",
        confirmation_token=token
    )
    assert res2["success"] is False
    assert res2["status"] in ("error", "PENDING_CONFIRMATION")
    assert res2["error_code"] == "TOKEN_ALREADY_USED"
    assert res2["requires_human_confirmation"] is True


def test_07_successful_sms_dispatch_and_audit_state():
    """Verify that successful SMS triggers audit status transition to DISPATCHED."""
    event = server.log_audit_trail(
        patient_id="P005",
        event_type="RESPIRATORY_DISTRESS",
        risk_level="CRITICAL",
        message="SpO2 dropped below 85% on room air.",
        phone="+15557778888"
    )
    event_id = event["event_id"]

    conf = server.confirm_escalation(event_id=event_id, confirmed_by="Dr. Beverly Crusher, MD")
    token = conf["confirmation_token"]

    res = server.trigger_emergency_sms(
        patient_id="P005",
        phone="+15557778888",
        message="URGENT: Supplemental oxygen required immediately.",
        confirmation_token=token
    )

    assert res["status"] == "DISPATCHED"
    assert res["dispatch_id"].startswith("MOCK-SMS-")
    assert res["phone"] == "+15557778888"

    # Verify audit record state
    trail = server.get_audit_trail(event_id)
    assert trail["audit_event"]["status"] == "DISPATCHED"
    assert trail["audit_event"]["dispatched_at"] is not None


def test_08_forced_send_failure_handling():
    """Verify that provider failure is caught, retried, and recorded as FAILED in audit log."""
    mock = get_mock_sender()
    mock.set_force_failure(True, reason="Simulated SMS gateway timeout")

    event = server.log_audit_trail(
        patient_id="P001",
        event_type="SEIZURE_ACTIVITY",
        risk_level="CRITICAL",
        message="Prolonged tonic-clonic seizure observed.",
        phone="+15559990000"
    )
    event_id = event["event_id"]

    conf = server.confirm_escalation(event_id=event_id, confirmed_by="Dr. Meredith Grey, MD")
    token = conf["confirmation_token"]

    res = server.trigger_emergency_sms(
        patient_id="P001",
        phone="+15559990000",
        message="Emergency medication administered.",
        confirmation_token=token
    )

    assert res["status"] == "FAILED"
    assert "Failed after 3 attempts" in res["error"]
    assert "Simulated SMS gateway timeout" in res["error"]

    # Audit log should show FAILED status and error details
    trail = server.get_audit_trail(event_id)
    assert trail["audit_event"]["status"] == "FAILED"
    assert "Simulated SMS gateway timeout" in trail["audit_event"]["error_details"]


def test_09_state_transition_guards_on_confirm_and_reject():
    """Verify that confirming or rejecting already-dispatched or rejected events fails with INVALID_STATE_TRANSITION."""
    event = server.log_audit_trail(
        patient_id="P002",
        event_type="HYPOGLYCEMIA",
        risk_level="HIGH",
        message="Blood glucose 42 mg/dL.",
        phone="+15552223333"
    )
    event_id = event["event_id"]

    # Reject the event
    rej = server.reject_escalation(
        event_id=event_id,
        rejected_by="Dr. Gregory House, MD",
        reason="False positive - patient consumed juice, repeat BG is 98 mg/dL"
    )
    assert rej["status"] == "REJECTED"

    # Attempting to confirm an already REJECTED event must fail
    invalid_conf = server.confirm_escalation(
        event_id=event_id,
        confirmed_by="Dr. Allison Cameron, MD"
    )
    assert invalid_conf["status"] == "error"
    assert invalid_conf["error_code"] == "INVALID_STATE_TRANSITION"
    assert "Cannot confirm event" in invalid_conf["message"]

    # Attempting to reject an already REJECTED event must also fail
    invalid_rej = server.reject_escalation(
        event_id=event_id,
        rejected_by="Dr. Eric Foreman, MD"
    )
    assert invalid_rej["status"] == "error"
    assert invalid_rej["error_code"] == "INVALID_STATE_TRANSITION"


def test_10_idempotency_guard():
    """Verify that retry logic does not double-send if message was already dispatched."""
    from notifications import send_sms_with_retry

    event = server.log_audit_trail(
        patient_id="P001",
        event_type="DIABETIC_KETOACIDOSIS",
        risk_level="CRITICAL",
        message="Ketones 4.2 mmol/L, pH 7.15.",
        phone="+15558889999"
    )
    event_id = event["event_id"]

    # First send
    success1, id1, meta1 = send_sms_with_retry(
        to_phone="+15558889999",
        message="DKA protocol initiated",
        event_id=event_id
    )
    assert success1 is True
    assert meta1.get("idempotent_replay", False) is False

    mock = get_mock_sender()
    assert len(mock.sent_messages) == 1

    # Second send for the EXACT same event_id and phone (e.g. timeout retry)
    success2, id2, meta2 = send_sms_with_retry(
        to_phone="+15558889999",
        message="DKA protocol initiated",
        event_id=event_id
    )
    assert success2 is True
    assert id2 == id1  # Same dispatch ID returned
    assert meta2.get("idempotent_replay") is True
    # Still only 1 message sent via carrier!
    assert len(mock.sent_messages) == 1


def test_11_list_pending_escalations():
    """Verify that listing pending escalations filters correctly."""
    server.log_audit_trail(
        patient_id="P001",
        event_type="ALERT_A",
        risk_level="HIGH",
        message="Pending Alert A",
        phone="+15551111111"
    )
    event_b = server.log_audit_trail(
        patient_id="P002",
        event_type="ALERT_B",
        risk_level="CRITICAL",
        message="Pending Alert B",
        phone="+15552222222"
    )

    pending = server.list_pending_escalations()
    assert pending["status"] == "success"
    assert pending["count"] >= 2

    # Now confirm event B
    server.confirm_escalation(event_id=event_b["event_id"], confirmed_by="Dr. Test, MD")

    # Re-check pending
    pending_after = server.list_pending_escalations()
    event_b_in_pending = any(e["event_id"] == event_b["event_id"] for e in pending_after["pending_escalations"])
    assert event_b_in_pending is False


def test_12_log_audit_trail_with_event_state_dict():
    """Verify that logging an event using an event_state dictionary works seamlessly."""
    event = server.log_audit_trail(
        patient_id="P001",
        event_state={
            "risk": "CRITICAL",
            "reason": "LOW_SPO2",
            "spo2": 86,
            "phone": "+15551234567"
        }
    )
    assert event["success"] is True
    assert event["event_type"] == "LOW_SPO2"
    assert event["risk_level"] == "CRITICAL"
    assert event["phone"] == "+15551234567"
    assert event["status"] == "PENDING_CONFIRMATION"
    assert event["requires_human_confirmation"] is True


def test_13_success_boolean_contracts():
    """Verify that all tools expose standardized success booleans and status keys."""
    evt = server.log_audit_trail("P001", "TEST_ALERT", "HIGH", "Testing success flag")
    assert evt["success"] is True

    # Blocked trigger
    blocked = server.trigger_emergency_sms("P001", "+15550001111", "msg", "")
    assert blocked["success"] is False
    assert blocked["status"] == "PENDING_CONFIRMATION"
    assert blocked["requires_human_confirmation"] is True

    # Confirm
    conf = server.confirm_escalation(evt["event_id"], "Dr. Tester, MD", phone="+15550001111")
    assert conf["success"] is True
    assert conf["status"] == "CONFIRMED"

    # Dispatch
    disp = server.trigger_emergency_sms("P001", "+15550001111", "msg", conf["confirmation_token"])
    assert disp["success"] is True
    assert disp["status"] == "DISPATCHED"


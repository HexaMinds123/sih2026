"""Unified Integration Test for EHR-MCP and Clinical-MCP.

Verifies end-to-end integration between:
1. Patient EHR & Context MCP Server (ehr-mcp)
2. Clinical Guidelines MCP Server (clinical-mcp)
3. Shared MongoDB Atlas infrastructure & collections
4. Dual-domain RAG retrieval (patient records + clinical guidelines)
5. Cross-server patient medication interaction safety checks
"""

import os
import sys
import importlib.util
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / "ehr-mcp" / ".env")


def load_module_from_path(name: str, file_path: Path):
    sys.path.insert(0, str(file_path.parent))
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ehr_server = load_module_from_path("ehr_server", ROOT / "ehr-mcp" / "server.py")
clinical_server = load_module_from_path("clinical_server", ROOT / "clinical-mcp" / "server.py")
notification_server = load_module_from_path("notification_server", ROOT / "notification-mcp" / "server.py")

TOKEN = "medical-agent-secret-token"


def run_integration_tests():
    print("=" * 70)
    print("  HEALTHCARE AI INTEGRATION VERIFICATION: EHR + CLINICAL + NOTIFICATION")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. Test EHR-MCP Resources & Tools
    # -------------------------------------------------------------------------
    print("\n[1/6] Testing EHR-MCP Data Access & Authentication...")
    profile = ehr_server.patient_profile("P001")
    assert profile["patient_id"] == "P001"
    print(f"  -> Profile loaded: {profile['name']} (Age {profile['age']}, {profile['gender']})")
    print(f"     Conditions: {profile['conditions']}")
    print(f"     Allergies: {profile['allergies']}")

    # Authenticated prescriptions
    rx_res = ehr_server.fetch_active_prescriptions("P001", TOKEN)
    assert rx_res["count"] > 0
    med_names = [r["drug"] for r in rx_res["prescriptions"]]
    print(f"  -> Active Prescriptions: {', '.join(med_names)}")

    # Unauthorized access rejection
    unauth = ehr_server.fetch_active_prescriptions("P001", "wrong-token")
    assert unauth["error"] is True and unauth["code"] == "UNAUTHORIZED"
    print("  -> Unauthorized access properly blocked with code UNAUTHORIZED")

    # -------------------------------------------------------------------------
    # 2. Test Clinical-MCP Tools
    # -------------------------------------------------------------------------
    print("\n[2/6] Testing Clinical-MCP Reference Guidance...")
    guidance = clinical_server.search_clinical_guidance("LOW_SPO2")
    assert guidance["found"] is True
    print(f"  -> Observation: {guidance['observation']}")
    print(f"  -> Recommended Action: {guidance['recommended_action']}")

    # -------------------------------------------------------------------------
    # 3. Test Patient RAG Semantic Search
    # -------------------------------------------------------------------------
    print("\n[3/6] Testing Patient EHR RAG Semantic Search...")
    patient_rag = ehr_server.search_patient_context(
        "patient with diabetes taking metformin and blood pressure medication",
        TOKEN,
        limit=3
    )
    assert patient_rag["count"] > 0
    top_p = patient_rag["results"][0]
    print(f"  -> Top Patient Match: {top_p['patient_id']} (Score: {top_p['score']})")
    print(f"     Snippet: {top_p['text'][:90]}...")

    # -------------------------------------------------------------------------
    # 4. Test Unified RAG Search (Patient + Clinical)
    # -------------------------------------------------------------------------
    print("\n[4/6] Testing Unified Semantic RAG Search across Both Domains...")
    unified = ehr_server.unified_search(
        "elevated heart rate tachycardia beta blocker",
        TOKEN,
        search_scope="both",
        limit=4
    )
    print(f"  -> Unified Query Matches Found: {unified['count']}")
    for idx, item in enumerate(unified["results"]):
        src = item.get("source", "unknown")
        score = item.get("score", 0.0)
        snippet = item.get("text", "")[:75]
        print(f"     [{idx+1}] Source: {src:<10} Score: {score:.4f} | {snippet}...")

    # -------------------------------------------------------------------------
    # 5. Test Cross-Server Patient Medication Safety Check
    # -------------------------------------------------------------------------
    print("\n[5/6] Testing Cross-Server Drug Safety Checking (EHR + Clinical)...")
    # Patient P003 is Marcus Vance, taking Warfarin and Aspirin
    p003_safety = ehr_server.check_patient_drug_safety("P003", TOKEN)
    print(f"  -> Patient P003 Active Meds: {p003_safety['active_medications']}")
    print(f"  -> Interaction Detected: {p003_safety['interaction_found']}")
    assert p003_safety["interaction_found"] is True
    for warn in p003_safety["interactions"]:
        print(f"     WARNING: {warn['drugs'][0]} + {warn['drugs'][1]}")
        print(f"     Severity: {warn['severity'].upper()} | Details: {warn['warning']}")

    # -------------------------------------------------------------------------
    # 6. Test End-to-End Escalation & Human Gate (Notification-MCP)
    # -------------------------------------------------------------------------
    print("\n[6/6] Testing Full Clinical Escalation & Human Confirmation Gate...")
    # Fetch P003 emergency contact from EHR
    p003_profile = ehr_server.patient_profile("P003")
    contact_phone = p003_profile.get("emergency_contact", {}).get("phone", "+15555550103")
    print(f"  -> Patient P003 Emergency Contact Phone: {contact_phone}")

    # Step A: Agent logs escalation event (Status: PENDING_CONFIRMATION)
    audit_evt = notification_server.log_audit_trail(
        patient_id="P003",
        event_type="MEDICATION_INTERACTION_CRITICAL",
        risk_level="CRITICAL",
        message="Co-administration of Warfarin and Aspirin detected; extreme hemorrhage risk.",
        phone=contact_phone
    )
    event_id = audit_evt["event_id"]
    print(f"  -> Escalation Event Logged: {event_id} (Status: {audit_evt['status']})")
    assert audit_evt["requires_human_confirmation"] is True

    # Step B: AI Agent tries to send SMS directly -> BLOCKED by gate
    blocked_dispatch = notification_server.trigger_emergency_sms(
        patient_id="P003",
        phone=contact_phone,
        message="EMERGENCY ALERT: Stop Aspirin immediately.",
        confirmation_token=""
    )
    print(f"  -> Direct SMS without token blocked: {blocked_dispatch['error_code']}")
    assert blocked_dispatch["success"] is False
    assert blocked_dispatch["status"] in ("error", "PENDING_CONFIRMATION")
    assert blocked_dispatch["requires_human_confirmation"] is True

    # Step C: Attending Doctor confirms escalation -> Mints 5-min token bound to contact_phone
    doctor_conf = notification_server.confirm_escalation(
        event_id=event_id,
        confirmed_by="Dr. Gregory House, MD",
        phone=contact_phone
    )
    token = doctor_conf["confirmation_token"]
    print(f"  -> Clinician confirmed: Token minted ({token[:18]}...), Expires: {doctor_conf['expires_at']}")
    assert doctor_conf["bound_phone"] == contact_phone

    # Step D: Phone tampering attempt -> Blocked by phone binding
    tamper_dispatch = notification_server.trigger_emergency_sms(
        patient_id="P003",
        phone="+15559998888",
        message="Tampered alert",
        confirmation_token=token
    )
    print(f"  -> Phone tampering blocked: {tamper_dispatch['error_code']}")
    assert tamper_dispatch["error_code"] == "PHONE_MISMATCH"

    # Step E: Legitimate dispatch with bound phone & token -> SUCCESS
    valid_dispatch = notification_server.trigger_emergency_sms(
        patient_id="P003",
        phone=contact_phone,
        message="CLINICAL ALERT: Doctor confirmed Warfarin/Aspirin risk. Please contact clinic.",
        confirmation_token=token
    )
    print(f"  -> Legitimate SMS Dispatched! Dispatch ID: {valid_dispatch['dispatch_id']}")
    assert valid_dispatch["status"] == "DISPATCHED"

    # Step F: Replay attack with same token -> BLOCKED (Token consumed)
    replay_dispatch = notification_server.trigger_emergency_sms(
        patient_id="P003",
        phone=contact_phone,
        message="Duplicate alert",
        confirmation_token=token
    )
    print(f"  -> Replay attack blocked: {replay_dispatch['error_code']}")
    assert replay_dispatch["error_code"] == "TOKEN_ALREADY_USED"

    # Step G: Check final audit trail
    final_trail = notification_server.get_audit_trail(event_id)
    assert final_trail["audit_event"]["status"] == "DISPATCHED"
    print(f"  -> Final Audit Status: {final_trail['audit_event']['status']} (Dispatched At: {final_trail['audit_event']['dispatched_at']})")

    print("\n" + "=" * 70)
    print("  ALL 3 MCP SERVERS & 6 INTEGRATION PHASES PASSED WITH ZERO ERRORS!")
    print("=" * 70)


if __name__ == "__main__":
    run_integration_tests()


"""
Escalation & Notification MCP Server (notification-mcp)

A production-grade Model Context Protocol (MCP) server managing healthcare emergency
escalations, tamper-evident audit trails, and multi-channel SMS notifications with an
enforced human-in-the-loop confirmation gate.

CRITICAL SAFETY INVARIANT:
The AI agent upstream CANNOT directly trigger emergency SMS alerts.
All SMS dispatches require a valid, single-use, phone-bound cryptographic confirmation
token minted explicitly by a human doctor/clinician through confirm_escalation().
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load local environment variables if available
load_dotenv(Path(__file__).parent / ".env", override=False)

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer as FastMCP
import sys
try:
    import database
    if not hasattr(database, "init_db") or not hasattr(database, "validate_and_consume_token"):
        raise AttributeError("Wrong database module loaded")
except (ImportError, AttributeError):
    import importlib.util
    _db_path = Path(__file__).resolve().parent / "database.py"
    _spec = importlib.util.spec_from_file_location("notification_mcp_database", _db_path)
    database = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(database)

try:
    from notifications import send_sms_with_retry
except (ImportError, AttributeError):
    import importlib.util
    _notif_path = Path(__file__).resolve().parent / "notifications.py"
    _spec = importlib.util.spec_from_file_location("notification_mcp_notifications", _notif_path)
    _notif_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_notif_mod)
    send_sms_with_retry = _notif_mod.send_sms_with_retry

# Initialize FastMCP Server
mcp = FastMCP("notification-mcp")

# Ensure database tables exist on startup
database.init_db()


@mcp.tool()
def log_audit_trail(
    patient_id: str,
    event_type: str = "",
    risk_level: str = "",
    message: str = "",
    phone: str = "",
    event_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Record an escalation or clinical event in the tamper-evident audit log.
    Sets the event status to 'PENDING_CONFIRMATION'.

    Supports both parameter styles:
    - Positional/keyword: log_audit_trail(patient_id, event_type, risk_level, message, phone)
    - Structured dictionary: log_audit_trail(patient_id, event_state={"risk": "CRITICAL", "reason": "LOW_SPO2", ...})

    Args:
        patient_id: The identifier of the patient (e.g., 'P001').
        event_type: The nature of the event (e.g., 'MEDICATION_ALERT', 'LOW_SPO2').
        risk_level: Assessed severity ('CRITICAL', 'HIGH', 'MODERATE', 'LOW').
        message: Description of the medical situation and recommended action.
        phone: Optional emergency contact phone number to pre-associate with the event.
        event_state: Optional structured dictionary containing risk, reason, vitals, etc.

    Returns:
        Structured event dictionary with event_id, success: True, and requires_human_confirmation: True.
    """
    # Unpack event_state dictionary if supplied
    if event_state and isinstance(event_state, dict):
        risk_level = risk_level or str(event_state.get("risk") or event_state.get("risk_level", "CRITICAL"))
        event_type = event_type or str(event_state.get("reason") or event_state.get("event_type", "CLINICAL_ALERT"))
        phone = phone or str(event_state.get("phone", ""))
        if not message:
            details = [f"{k}={v}" for k, v in event_state.items() if k not in ("risk", "risk_level", "reason", "event_type", "phone")]
            message = f"{event_type}: {', '.join(details)}" if details else f"Clinical event: {event_type}"

    resolved_event_type = (event_type or "CLINICAL_ALERT").strip()
    resolved_risk_level = (risk_level or "CRITICAL").strip().upper()
    resolved_message = (message or f"Escalation event {resolved_event_type}").strip()

    event = database.create_event(
        patient_id=patient_id.strip(),
        event_type=resolved_event_type,
        risk_level=resolved_risk_level,
        message=resolved_message,
        phone=phone.strip() if phone else None
    )
    event["success"] = True
    return event


@mcp.tool()
def list_pending_escalations() -> Dict[str, Any]:
    """
    List all clinical escalation events currently awaiting human review and confirmation.

    Returns:
        Dictionary containing a list of pending escalation records and total count.
    """
    pending = database.list_pending_events()
    return {
        "success": True,
        "status": "success",
        "count": len(pending),
        "pending_escalations": pending
    }


@mcp.tool()
def confirm_escalation(
    event_id: str,
    confirmed_by: str,
    phone: str = ""
) -> Dict[str, Any]:
    """
    Human-in-the-loop authorization gate.
    A licensed clinician or operator reviews the pending event and confirms it.
    This mints a single-use, phone-bound cryptographic confirmation token with a 5-minute expiry.

    Guards:
      - Rejects with INVALID_STATE_TRANSITION if event is already CONFIRMED, DISPATCHED, or REJECTED.
      - Binds the token strictly to the emergency contact phone number to prevent replay attacks.

    Args:
        event_id: The ID of the pending escalation event (e.g. 'EVENT-20260909-ABCD').
        confirmed_by: Identity of the confirming human clinician (e.g., 'Dr. Jane Smith, MD').
        phone: Recipient emergency phone number (if not already set in the audit event).

    Returns:
        Confirmation details including the single-use confirmation_token, bound_phone, and expires_at.
    """
    success, result = database.confirm_event(
        event_id=event_id.strip(),
        confirmed_by=confirmed_by.strip(),
        phone=phone.strip() if phone else None
    )
    result["success"] = success
    return result


@mcp.tool()
def reject_escalation(
    event_id: str,
    rejected_by: str,
    reason: str = ""
) -> Dict[str, Any]:
    """
    Decline an escalation event after clinician review.
    Marks the audit event status as 'REJECTED'.

    Guards:
      - Rejects with INVALID_STATE_TRANSITION if event is not currently in PENDING_CONFIRMATION.

    Args:
        event_id: The ID of the pending escalation event.
        rejected_by: Identity of the reviewing human clinician (e.g., 'Dr. Jane Smith, MD').
        reason: Clinical justification for rejecting the alert.

    Returns:
        Dictionary confirming event status change to REJECTED.
    """
    success, result = database.reject_event(
        event_id=event_id.strip(),
        rejected_by=rejected_by.strip(),
        reason=reason.strip() if reason else None
    )
    result["success"] = success
    return result


@mcp.tool()
def trigger_emergency_sms(
    patient_id: str,
    phone: str,
    message: str,
    confirmation_token: str,
    event_id: str = ""
) -> Dict[str, Any]:
    """
    Dispatch an emergency SMS notification to a verified caregiver or doctor.

    HARD SAFETY ENFORCEMENT:
      1. Requires a valid, unconsumed confirmation_token minted by confirm_escalation().
      2. Validates that the token has not expired (5-minute validity window).
      3. Validates that the token belongs to the specified patient_id.
      4. Validates that the token is strictly bound to the target phone number (PHONE_MISMATCH check).
      5. Consumes the token immediately upon validation to prevent replay attacks.
      6. Applies idempotency protection to prevent duplicate sends during network timeouts.

    Args:
        patient_id: The patient identifier.
        phone: The destination phone number in E.164 format (e.g., '+15551234567').
        message: The emergency SMS body.
        confirmation_token: The cryptographic token obtained from human confirmation.
        event_id: Optional event ID (derived automatically from the token if omitted).

    Returns:
        Structured result indicating dispatch status ('DISPATCHED' or 'FAILED') and audit details.
    """
    # Phase 1: Cryptographic Human Confirmation Verification
    valid, token_data = database.validate_and_consume_token(
        token=confirmation_token.strip() if confirmation_token else "",
        patient_id=patient_id.strip(),
        phone=phone.strip()
    )

    if not valid:
        # Rejection: unauthorized or invalid token
        return {
            "success": False,
            "status": "PENDING_CONFIRMATION",
            "error_code": token_data.get("error_code", "CONFIRMATION_REQUIRED"),
            "message": token_data.get("message", "Human confirmation required before dispatching emergency alerts."),
            "requires_human_confirmation": True
        }

    # Phase 2: Resolve Event Context
    bound_event_id = token_data.get("event_id")
    target_event_id = event_id.strip() if event_id else bound_event_id

    # Phase 3: Dispatch SMS with Retry Policy and Idempotency Guard
    success, dispatch_id_or_err, metadata = send_sms_with_retry(
        to_phone=phone.strip(),
        message=message.strip(),
        event_id=target_event_id
    )

    if success:
        return {
            "success": True,
            "status": "DISPATCHED",
            "event_id": target_event_id,
            "patient_id": patient_id.strip(),
            "phone": phone.strip(),
            "dispatch_id": dispatch_id_or_err,
            "provider": metadata.get("provider", "mock"),
            "attempts": metadata.get("attempts", 1),
            "idempotent_replay": metadata.get("idempotent_replay", False),
            "message": "Emergency SMS successfully dispatched."
        }
    else:
        return {
            "success": False,
            "status": "FAILED",
            "event_id": target_event_id,
            "patient_id": patient_id.strip(),
            "phone": phone.strip(),
            "error": dispatch_id_or_err,
            "attempts": metadata.get("attempts", 3),
            "message": "Emergency SMS dispatch failed after retry attempts. Logged in audit trail."
        }


@mcp.tool()
def get_audit_trail(event_id: str) -> Dict[str, Any]:
    """
    Query the complete audit trail entry for an escalation event.

    Args:
        event_id: The escalation event ID to inspect.

    Returns:
        The full audit log entry or an error if not found.
    """
    event = database.get_event(event_id.strip())
    if not event:
        return {
            "status": "error",
            "error_code": "EVENT_NOT_FOUND",
            "message": f"Audit record for event '{event_id}' not found."
        }
    return {
        "status": "success",
        "audit_event": event
    }


if __name__ == "__main__":
    mcp.run()

"""
Notification MCP Server - Audit & Confirmation Database Layer
Manages SQLite storage for tamper-evident audit logs, single-use confirmation tokens,
and dispatch idempotency tracking.
"""

import os
import sqlite3
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "audit.db"
DEFAULT_TOKEN_EXPIRY_SECONDS = 300  # 5 minutes


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path or Path(os.environ.get("NOTIFICATION_DB_PATH", str(DEFAULT_DB_PATH)))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables for audit logging, tokens, and idempotency."""
    conn = get_db_connection(db_path)
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                event_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                message TEXT NOT NULL,
                phone TEXT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                confirmed_by TEXT,
                dispatched_at TEXT,
                error_details TEXT
            );

            CREATE TABLE IF NOT EXISTS confirmation_tokens (
                token TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                FOREIGN KEY (event_id) REFERENCES audit_logs(event_id)
            );

            CREATE TABLE IF NOT EXISTS idempotent_dispatches (
                idempotency_key TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                phone TEXT NOT NULL,
                status TEXT NOT NULL,
                provider_message_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_logs(patient_id);
            CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_logs(status);
            CREATE INDEX IF NOT EXISTS idx_token_event ON confirmation_tokens(event_id);
        """)
    conn.close()


def create_event(
    patient_id: str,
    event_type: str,
    risk_level: str,
    message: str,
    phone: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Create a new pending escalation event in the audit trail."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_hex = secrets.token_hex(4).upper()
    event_id = f"EVENT-{date_str}-{random_hex}"
    status = "PENDING_CONFIRMATION"

    with conn:
        conn.execute(
            """
            INSERT INTO audit_logs (
                event_id, patient_id, event_type, risk_level, message, phone, timestamp, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, patient_id, event_type, risk_level, message, phone or "", now_iso, status)
        )
    conn.close()

    return {
        "event_id": event_id,
        "patient_id": patient_id,
        "event_type": event_type,
        "risk_level": risk_level,
        "message": message,
        "phone": phone or "",
        "timestamp": now_iso,
        "status": status,
        "requires_human_confirmation": True
    }


def get_event(event_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve an audit event record by event_id."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT * FROM audit_logs WHERE event_id = ?", (event_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_pending_events(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve all escalation events awaiting human confirmation."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM audit_logs WHERE status = 'PENDING_CONFIRMATION' ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def confirm_event(
    event_id: str,
    confirmed_by: str,
    phone: Optional[str] = None,
    expiry_seconds: int = DEFAULT_TOKEN_EXPIRY_SECONDS,
    db_path: Optional[Path] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Confirm an escalation event and mint a single-use, phone-bound token with explicit expiry.
    Fails with structured error if event is not in PENDING_CONFIRMATION status.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT * FROM audit_logs WHERE event_id = ?", (event_id,)).fetchone()

    if not row:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "EVENT_NOT_FOUND",
            "message": f"Escalation event '{event_id}' not found."
        }

    current_status = row["status"]
    if current_status != "PENDING_CONFIRMATION":
        conn.close()
        return False, {
            "status": "error",
            "error_code": "INVALID_STATE_TRANSITION",
            "message": f"Cannot confirm event '{event_id}' with status '{current_status}'. Event must be in 'PENDING_CONFIRMATION'."
        }

    # Determine and validate bound phone number
    bound_phone = (phone or row["phone"] or "").strip()
    if not bound_phone:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "MISSING_PHONE",
            "message": f"Cannot confirm escalation '{event_id}' without an emergency recipient phone number."
        }

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expiry_seconds)
    token = f"tok_{secrets.token_urlsafe(32)}"

    with conn:
        # Mint token binding event, patient, and recipient phone
        conn.execute(
            """
            INSERT INTO confirmation_tokens (
                token, event_id, patient_id, phone, created_at, expires_at, used
            ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (token, event_id, row["patient_id"], bound_phone, now.isoformat(), expires_at.isoformat())
        )
        # Update audit status to CONFIRMED
        conn.execute(
            """
            UPDATE audit_logs
            SET status = 'CONFIRMED', confirmed_by = ?, phone = ?
            WHERE event_id = ?
            """,
            (confirmed_by, bound_phone, event_id)
        )
    conn.close()

    return True, {
        "status": "CONFIRMED",
        "event_id": event_id,
        "patient_id": row["patient_id"],
        "confirmed_by": confirmed_by,
        "bound_phone": bound_phone,
        "confirmation_token": token,
        "expires_at": expires_at.isoformat(),
        "validity_seconds": expiry_seconds,
        "message": f"Escalation confirmed by {confirmed_by}. Single-use token generated (valid for {expiry_seconds // 60} minutes)."
    }


def reject_event(
    event_id: str,
    rejected_by: str,
    reason: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Reject an escalation event.
    Fails with structured error if event is not in PENDING_CONFIRMATION status.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT * FROM audit_logs WHERE event_id = ?", (event_id,)).fetchone()

    if not row:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "EVENT_NOT_FOUND",
            "message": f"Escalation event '{event_id}' not found."
        }

    current_status = row["status"]
    if current_status != "PENDING_CONFIRMATION":
        conn.close()
        return False, {
            "status": "error",
            "error_code": "INVALID_STATE_TRANSITION",
            "message": f"Cannot reject event '{event_id}' with status '{current_status}'. Event must be in 'PENDING_CONFIRMATION'."
        }

    error_detail = f"Rejected by {rejected_by}: {reason}" if reason else f"Rejected by {rejected_by}"

    with conn:
        conn.execute(
            """
            UPDATE audit_logs
            SET status = 'REJECTED', confirmed_by = ?, error_details = ?
            WHERE event_id = ?
            """,
            (rejected_by, error_detail, event_id)
        )
    conn.close()

    return True, {
        "status": "REJECTED",
        "event_id": event_id,
        "patient_id": row["patient_id"],
        "rejected_by": rejected_by,
        "reason": reason or "No reason provided",
        "message": f"Escalation {event_id} has been marked as REJECTED."
    }


def validate_and_consume_token(
    token: str,
    patient_id: str,
    phone: str,
    db_path: Optional[Path] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate and immediately consume a single-use confirmation token.
    Enforces:
      - Existence
      - Single-use flag (prevents replay attack)
      - Explicit expiration (default 5 min)
      - Patient binding
      - Phone number binding (prevents redirecting alert to unauthorized phone)
    """
    if not token or not token.strip():
        return False, {
            "status": "error",
            "error_code": "MISSING_TOKEN",
            "message": "Human confirmation token is required to dispatch emergency SMS.",
            "requires_human_confirmation": True
        }

    init_db(db_path)
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT * FROM confirmation_tokens WHERE token = ?", (token.strip(),)).fetchone()

    if not row:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "INVALID_TOKEN",
            "message": "Confirmation token is invalid or does not exist.",
            "requires_human_confirmation": True
        }

    # 1. Single-use guard
    if row["used"] == 1:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "TOKEN_ALREADY_USED",
            "message": "Confirmation token has already been consumed. Replay attacks are prohibited.",
            "requires_human_confirmation": True
        }

    # 2. Expiration guard
    expires_at = datetime.fromisoformat(row["expires_at"])
    now = datetime.now(timezone.utc)
    if now > expires_at:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "TOKEN_EXPIRED",
            "message": f"Confirmation token expired at {row['expires_at']}. Re-confirmation by a clinician is required.",
            "requires_human_confirmation": True
        }

    # 3. Patient binding guard
    if row["patient_id"] != patient_id:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "PATIENT_MISMATCH",
            "message": f"Token belongs to patient '{row['patient_id']}', but caller requested dispatch for '{patient_id}'.",
            "requires_human_confirmation": True
        }

    # 4. Phone binding guard
    bound_phone = row["phone"].strip()
    target_phone = phone.strip()
    if bound_phone and bound_phone != target_phone:
        conn.close()
        return False, {
            "status": "error",
            "error_code": "PHONE_MISMATCH",
            "message": f"Token is strictly bound to phone '{bound_phone}', but caller supplied '{target_phone}'. Dispatch rejected.",
            "requires_human_confirmation": True
        }

    # Consume the token atomically with conditional concurrency guard
    with conn:
        cursor = conn.execute(
            "UPDATE confirmation_tokens SET used = 1 WHERE token = ? AND used = 0",
            (token.strip(),)
        )
        if cursor.rowcount == 0:
            conn.close()
            return False, {
                "status": "error",
                "error_code": "TOKEN_ALREADY_USED",
                "message": "Confirmation token has already been consumed. Replay attacks are prohibited.",
                "requires_human_confirmation": True
            }
    conn.close()

    return True, dict(row)


def check_idempotency(
    event_id: str,
    phone: str,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Check if an SMS dispatch has already succeeded for this event and phone."""
    idempotency_key = f"{event_id}:{phone.strip()}"
    init_db(db_path)
    conn = get_db_connection(db_path)
    row = conn.execute(
        "SELECT * FROM idempotent_dispatches WHERE idempotency_key = ?",
        (idempotency_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def record_dispatch_result(
    event_id: str,
    phone: str,
    status: str,
    provider_message_id: Optional[str] = None,
    error_details: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """Record dispatch outcome in audit_logs and idempotent_dispatches."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    idempotency_key = f"{event_id}:{phone.strip()}"

    with conn:
        conn.execute(
            """
            UPDATE audit_logs
            SET status = ?, dispatched_at = ?, error_details = ?
            WHERE event_id = ?
            """,
            (status, now_iso, error_details, event_id)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO idempotent_dispatches (
                idempotency_key, event_id, phone, status, provider_message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (idempotency_key, event_id, phone.strip(), status, provider_message_id, now_iso)
        )
    conn.close()

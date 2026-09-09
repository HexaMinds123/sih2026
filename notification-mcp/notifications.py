"""
Notification MCP Server - SMS Dispatch & Notification Provider
Handles SMS delivery using either Mock Provider (default for testing/dev)
or Twilio API with exponential backoff retries and idempotency guards.
"""

import os
import sys
import time
import uuid
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

try:
    import database as db_mod
    if not hasattr(db_mod, "check_idempotency"):
        raise AttributeError("Wrong database module loaded")
except (ImportError, AttributeError):
    import importlib.util
    _db_path = Path(__file__).resolve().parent / "database.py"
    _spec = importlib.util.spec_from_file_location("notification_mcp_database", _db_path)
    db_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(db_mod)

check_idempotency = db_mod.check_idempotency
record_dispatch_result = db_mod.record_dispatch_result

logger = logging.getLogger("notification-mcp.notifications")


class MockSMSSender:
    """Mock SMS provider for local testing and hackathon demonstrations."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.force_failure: bool = False
        self.failure_reason: str = "Simulated carrier routing failure"

    def set_force_failure(self, should_fail: bool, reason: str = "Simulated carrier routing failure"):
        """Enable or disable simulated failure for testing."""
        self.force_failure = should_fail
        self.failure_reason = reason

    def send(self, to_phone: str, message: str) -> str:
        """Send simulated SMS. Returns message ID or raises Exception."""
        if self.force_failure:
            raise RuntimeError(f"Carrier Error: {self.failure_reason}")

        msg_id = f"MOCK-SMS-{uuid.uuid4().hex[:12].upper()}"
        record = {
            "message_id": msg_id,
            "to_phone": to_phone,
            "message": message,
            "timestamp": time.time(),
            "status": "delivered"
        }
        self.sent_messages.append(record)
        return msg_id


class TwilioSMSSender:
    """Production Twilio SMS provider."""

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not (self.account_sid and self.auth_token and self.from_number):
                raise ValueError("Twilio credentials missing. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER.")
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    def send(self, to_phone: str, message: str) -> str:
        """Send SMS via Twilio REST API. Returns message SID."""
        client = self._get_client()
        msg = client.messages.create(
            body=message,
            from_=self.from_number,
            to=to_phone
        )
        return msg.sid


# Global provider instances
_mock_sender = MockSMSSender()
_twilio_sender = TwilioSMSSender()


def get_active_sender():
    """Return the active SMS sender based on environment config."""
    enable_twilio = os.environ.get("ENABLE_TWILIO", "false").strip().lower() in ("1", "true", "yes")
    if enable_twilio:
        return _twilio_sender
    return _mock_sender


def get_mock_sender() -> MockSMSSender:
    """Direct access to mock sender for test configuration."""
    return _mock_sender


def send_sms_with_retry(
    to_phone: str,
    message: str,
    event_id: str,
    max_retries: int = 3,
    db_path = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Send an emergency SMS with exponential backoff and idempotency verification.

    Idempotency Guard:
    Checks if a message for this event_id and phone was already successfully dispatched.
    If yes, returns the existing dispatch ID without double-sending (protects against
    duplicate delivery on network response timeouts).

    Returns:
      (success: bool, dispatch_id_or_error: str, metadata: dict)
    """
    # 1. Idempotency verification
    existing_dispatch = check_idempotency(event_id, to_phone, db_path=db_path)
    if existing_dispatch and existing_dispatch.get("status") == "DISPATCHED":
        provider_id = existing_dispatch.get("provider_message_id", "ALREADY_DISPATCHED")
        return True, provider_id, {
            "idempotent_replay": True,
            "previous_dispatch": existing_dispatch,
            "message": "SMS was already dispatched for this event; returned existing dispatch record."
        }

    sender = get_active_sender()
    last_exception = None
    attempts = 0

    for attempt in range(1, max_retries + 1):
        attempts = attempt
        try:
            dispatch_id = sender.send(to_phone=to_phone, message=message)
            # Record successful dispatch
            record_dispatch_result(
                event_id=event_id,
                phone=to_phone,
                status="DISPATCHED",
                provider_message_id=dispatch_id,
                error_details=None,
                db_path=db_path
            )
            return True, dispatch_id, {
                "attempts": attempts,
                "provider": "twilio" if isinstance(sender, TwilioSMSSender) else "mock",
                "dispatch_id": dispatch_id
            }
        except Exception as exc:
            last_exception = exc
            logger.warning(f"SMS attempt {attempt}/{max_retries} failed for event {event_id}: {exc}")
            if attempt < max_retries:
                # Exponential backoff: 0.1s, 0.2s, 0.4s (keeps test and emergency latency tight)
                backoff_time = 0.1 * (2 ** (attempt - 1))
                time.sleep(backoff_time)

    # If all attempts fail:
    error_msg = f"Failed after {attempts} attempts: {str(last_exception)}"
    record_dispatch_result(
        event_id=event_id,
        phone=to_phone,
        status="FAILED",
        provider_message_id=None,
        error_details=error_msg,
        db_path=db_path
    )
    return False, error_msg, {
        "attempts": attempts,
        "provider": "twilio" if isinstance(sender, TwilioSMSSender) else "mock",
        "error": str(last_exception)
    }

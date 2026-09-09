# Escalation & Notification MCP Server (`notification-mcp`)

A production-grade Model Context Protocol (MCP) server managing healthcare emergency escalations, tamper-evident audit trails, and multi-channel SMS notifications with an **enforced human-in-the-loop confirmation gate**.

---

## 🚨 Architectural Invariant & Safety Guard

In a clinical AI system, the Notification Server is the **most dangerous component** because it can trigger real-world actions (dispatching emergency SMS messages to caregivers and attending physicians).

### The Invariant:
> **The AI agent upstream CANNOT directly trigger emergency SMS alerts.**
>
> Risk assessment happens upstream in the orchestrator. This server only executes communication **after** an authorized clinician explicitly reviews and confirms the escalation event.

```
+------------------+         1. Log Event (PENDING)        +--------------------+
|  AI Orchestrator | ----------------------------------->  |  notification-mcp  |
+------------------+                                       +--------------------+
         |                                                           |
         | 2. Direct SMS blocked without token                       |
         X (requires_human_confirmation: true)                       |
                                                                     |
+------------------+         3. confirm_escalation()                 |
|  Human Doctor/   | ----------------------------------->  [Mints single-use]
|  Clinician       | <-----------------------------------  [token bound to ]
+------------------+     Token (5-min expiry, phone bound) [phone & patient]
         |
         | 4. Passes token to Orchestrator / UI
         v
+------------------+         5. trigger_emergency_sms()
|  AI / Caller     | ----------------------------------->  [Validates & burns token]
+------------------+                                       [Checks idempotency    ]
                                                           [Dispatches via Twilio/Mock]
                                                                     |
                                                                     v
                                                            +---------------+
                                                            | Caregiver/Doc |
                                                            | Mobile Phone  |
                                                            +---------------+
```

---

## 🔒 Security & Reliability Guarantees

### 1. Token Phone Binding
- Confirmation tokens bind the recipient `phone` at mint-time in `confirmation_tokens`.
- If a caller attempts to use a token with a different phone number, the server immediately aborts the dispatch with `error_code: "PHONE_MISMATCH"`.
- This eliminates replay attacks where a doctor-approved token for patient `P001` is redirected to an unauthorized phone number.

### 2. Explicit Token Expiry Window
- Tokens are short-lived, with a default validity window of **5 minutes (300 seconds)** (`TOKEN_EXPIRY_SECONDS=300`).
- Expired tokens cannot be used and return `error_code: "TOKEN_EXPIRED"`, requiring clinician re-evaluation.

### 3. Single-Use Replay Prevention
- Every confirmation token is burned (`used = 1`) immediately upon verification before SMS transmission.
- Re-submitting the same token yields `error_code: "TOKEN_ALREADY_USED"`.

### 4. Idempotency Guard on Retries
- Dispatches are tracked by an idempotency key (`event_id:phone`).
- If an SMS provider call succeeds but the client experiences a connection timeout, subsequent retries return the existing dispatch record rather than double-sending SMS messages.

### 5. Strict State Transition Enforcement
- Events begin in `PENDING_CONFIRMATION`.
- `confirm_escalation` and `reject_escalation` reject transitions on events that are already `CONFIRMED`, `DISPATCHED`, `FAILED`, or `REJECTED` with `error_code: "INVALID_STATE_TRANSITION"`.

### 6. Zero Committed Secrets
- `.env` is covered by root `.gitignore`. Only `.env.example` ships in the repository.

---

## 🛠️ MCP Tools

| Tool | Purpose | Security Gate |
|------|---------|---------------|
| `log_audit_trail` | Records emergency event with status `PENDING_CONFIRMATION` | None (Open to AI) |
| `list_pending_escalations` | Lists events awaiting human clinician review | Read-only |
| `confirm_escalation` | Human clinician approves event, minting single-use token | Requires `confirmed_by` |
| `reject_escalation` | Human clinician declines event with reason | Requires `rejected_by` |
| `trigger_emergency_sms` | Dispatches SMS via carrier provider | **Enforces single-use phone-bound token** |
| `get_audit_trail` | Inspects full lifecycle and dispatch log for an event | Read-only |

---

## 📦 Setup & Configuration

### Prerequisites
- Python 3.10+
- `mcp>=1.2.0`
- `twilio>=8.0.0` (optional, for live SMS delivery)

### Environment Variables
Copy `.env.example` to `.env` for local configuration:
```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTIFICATION_DB_PATH` | `audit.db` | Path to SQLite audit database |
| `TOKEN_EXPIRY_SECONDS` | `300` | Token expiration window in seconds |
| `ENABLE_TWILIO` | `false` | Set to `true` to deliver live SMS via Twilio |
| `TWILIO_ACCOUNT_SID` | - | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | - | Twilio Auth Token |
| `TWILIO_FROM_NUMBER` | - | Twilio registered sender phone |

### Claude Desktop Configuration
Add this server to your Claude Desktop config (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "notification-mcp": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "d:\\sih2026\\notification-mcp",
      "env": {
        "NOTIFICATION_DB_PATH": "audit.db",
        "TOKEN_EXPIRY_SECONDS": "300",
        "ENABLE_TWILIO": "false"
      }
    }
  }
}
```

---

## 🧪 Testing

Run the comprehensive pytest suite covering all 11 security and lifecycle requirements:

```bash
cd notification-mcp
python -m pytest test_notification_mcp.py -v
```

### Test Coverage:
1. `test_01_log_audit_trail`: Records `PENDING_CONFIRMATION` event.
2. `test_02_direct_sms_without_token_is_blocked`: Autonomous send blocked with `MISSING_TOKEN` / `INVALID_TOKEN`.
3. `test_03_confirm_escalation_mints_token_and_binds_phone`: Clinician generates phone-bound 5-min token.
4. `test_04_token_phone_binding_prevents_phone_tampering`: Replay to alternate number rejected with `PHONE_MISMATCH`.
5. `test_05_token_expiry_guard`: Expired token rejected with `TOKEN_EXPIRED`.
6. `test_06_single_use_token_replay_attack_prevention`: Used token rejected with `TOKEN_ALREADY_USED`.
7. `test_07_successful_sms_dispatch_and_audit_state`: SMS dispatch updates audit status to `DISPATCHED`.
8. `test_08_forced_send_failure_handling`: Carrier error retries and updates audit status to `FAILED`.
9. `test_09_state_transition_guards_on_confirm_and_reject`: Confirmed/rejected events reject invalid state changes.
10. `test_10_idempotency_guard`: Duplicate dispatches reuse existing message ID.
11. `test_11_list_pending_escalations`: Correctly queries pending queue.

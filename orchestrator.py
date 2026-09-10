"""
Healthcare AI Orchestrator Agent

Coordinates the three independent MCP servers:
1. EHR-MCP: Retrieves patient medical context (demographics, conditions, prescriptions).
2. Clinical-MCP: Retrieves evidence-based clinical guidelines and drug interaction matrices.
3. Notification-MCP: Handles audit logging, human confirmation gates, and SMS dispatches.

Also integrates the Medical & Pharmaceutical Agent (prescription-system) via
MedicalAgentAdapter for deterministic prescription analysis.

SAFETY ARCHITECTURE:
- Risk evaluation is performed here in the Orchestrator.
- Notification-MCP never decides if an emergency exists.
- Real-world external communication is blocked until an attending clinician explicitly confirms.
- INFORMATIONAL prescriptions are never auto-approved (approved=False always; Safety Invariant #3).
- All statuses require human_review_required=True through evaluate_prescription().
"""

from __future__ import annotations

import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

# Load environment configuration
load_dotenv(ROOT / "ehr-mcp" / ".env", override=False)


def _load_server_module(name: str, server_path: Path):
    """Dynamically load an MCP server module without namespace collision."""
    import importlib.util
    if str(server_path.parent) not in sys.path:
        sys.path.insert(0, str(server_path.parent))
    spec = importlib.util.spec_from_file_location(name, server_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load independent MCP servers
_ehr = _load_server_module("orchestrator_ehr", ROOT / "ehr-mcp" / "server.py")
_clinical = _load_server_module("orchestrator_clinical", ROOT / "clinical-mcp" / "server.py")
_notification = _load_server_module("orchestrator_notification", ROOT / "notification-mcp" / "server.py")

DEFAULT_TOKEN = os.getenv("AGENT_API_TOKEN", "medical-agent-secret-token")

# ---------------------------------------------------------------------------
# Structured degradation dict returned when the adapter is unavailable or
# when analyze_prescription raises any unhandled exception.
# ---------------------------------------------------------------------------
_DEGRADED = {
    "available": False,
    "status": "INSUFFICIENT_INFORMATION",
    "human_review_required": True,
    "issues": [],
    "drug_interactions": {"interaction_found": False, "interactions": []},
    "medications": [],
}


class MedicalAgentAdapter:
    """
    Thin integration boundary between HealthcareOrchestrator and the
    Medical & Pharmaceutical Agent (prescription-system/app/medical_agent.py).

    Responsibilities:
    - Safe import of analyze_prescription and Pydantic models from the
      prescription-system package, without polluting sys.modules globally.
    - Sync/async bridging: analyze_prescription is async; this adapter
      exposes a synchronous run() usable from non-async orchestrator code.
    - Input polymorphism: accepts ExtractionResponse, dict, or keyword args.
    - Graceful degradation: any import error or runtime exception is caught
      and returned as a structured dict (never re-raised to the caller).
    """

    def __init__(self) -> None:
        self.available = False
        self._analyze_prescription = None
        self._ExtractionResponse = None
        self._AnalysisResponse = None
        self._Medication = None
        self._Patient = None
        self._Prescription = None
        self._OCRResult = None
        self._import_error: str = ""

        _rx_root = ROOT / "prescription-system"
        _rx_str = str(_rx_root)

        try:
            # Inject prescription-system into sys.path if not already present
            # so that `from app.xxx import ...` resolves correctly.
            if _rx_str not in sys.path:
                sys.path.insert(0, _rx_str)

            from app.medical_agent import analyze_prescription  # noqa: PLC0415
            from app.models import (  # noqa: PLC0415
                AnalysisResponse,
                ExtractionResponse,
                Medication,
                OCRResult,
                Patient,
                Prescription,
            )

            self._analyze_prescription = analyze_prescription
            self._ExtractionResponse = ExtractionResponse
            self._AnalysisResponse = AnalysisResponse
            self._Medication = Medication
            self._Patient = Patient
            self._Prescription = Prescription
            self._OCRResult = OCRResult
            self.available = True

        except Exception as exc:  # pylint: disable=broad-except
            self._import_error = str(exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _degraded(self, reason: str) -> Dict[str, Any]:
        """Return a copy of the degradation dict with the supplied reason appended."""
        result = dict(_DEGRADED)
        result["issues"] = [reason]
        return result

    def _build_extraction(self, **kwargs) -> Any:
        """
        Build an ExtractionResponse from keyword arguments when the caller
        supplies raw prescription parameters instead of a model instance.

        Supported kwargs: prescription_id, medications (list of dicts),
        condition, patient_name, patient_age, patient_gender.
        """
        ExtractionResponse = self._ExtractionResponse
        Medication = self._Medication
        Patient = self._Patient
        Prescription = self._Prescription
        OCRResult = self._OCRResult

        prescription_id = kwargs.get("prescription_id", "RX-UNKNOWN")
        condition = kwargs.get("condition")
        raw_meds = kwargs.get("medications", [])

        meds = []
        for m in raw_meds:
            if isinstance(m, dict):
                meds.append(Medication(**{k: v for k, v in m.items() if k in Medication.model_fields}))
            elif isinstance(m, self._Medication):
                meds.append(m)

        patient = Patient(
            name=kwargs.get("patient_name"),
            age=kwargs.get("patient_age"),
            gender=kwargs.get("patient_gender"),
        )
        prescription = Prescription(
            patient=patient,
            condition=condition,
            medications=meds,
        )
        ocr = OCRResult(raw_text="", human_verification_required=False)
        return ExtractionResponse(
            prescription_id=prescription_id,
            ocr=ocr,
            prescription=prescription,
            human_verification_required=False,
        )

    def _run_async(self, extraction: Any) -> Any:
        """
        Execute analyze_prescription(extraction) bridging sync → async.
        Execute analyze_prescription(extraction) bridging sync -> async.

        Strategy:
        - If no running event loop: use asyncio.run() (standard path).
        - If a loop IS running (e.g., inside FastAPI or an async test):
          submit to a fresh ThreadPoolExecutor thread that owns its own
          event loop, avoiding 'This event loop is already running'.
        asyncio.get_running_loop() raises RuntimeError when there is NO running
        loop. So:
          - RuntimeError caught  => no loop running  => asyncio.run() is safe.
          - No exception         => loop IS running   => must delegate to a thread
            that owns its own loop to avoid "This event loop is already running".

        IMPORTANT: the coroutine must be created *inside* the worker thread
        (via the lambda), not in the calling thread, to avoid cross-thread
        coroutine sharing which is unsafe in CPython's asyncio.
        """
        coro_factory = lambda: self._analyze_prescription(extraction)  # noqa: E731

        try:
            asyncio.get_running_loop()
            # A loop is already running — delegate to a thread with its own loop.
            # Loop is running (e.g. FastAPI, async pytest) — use a thread.
            import concurrent.futures  # noqa: PLC0415
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro_factory())
                future = pool.submit(
                    lambda: asyncio.run(self._analyze_prescription(extraction))
                )
                return future.result()
        except RuntimeError:
            # No running loop — safe to call asyncio.run() directly.
            return asyncio.run(coro_factory())
            # No running loop — standard sync call path.
            return asyncio.run(self._analyze_prescription(extraction))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, extraction: Any = None, **kwargs) -> Any:
        """
        Invoke the Medical Agent and return an AnalysisResponse (or the
        structured degradation dict if unavailable or on any error).

        Args:
            extraction: ExtractionResponse instance, a dict to be validated
                        via ExtractionResponse.model_validate(), or None when
                        keyword prescription params are supplied instead.
            **kwargs:   Keyword prescription params forwarded to _build_extraction()
                        when extraction is None (e.g. medications=[], condition=...).

        Returns:
            AnalysisResponse on success; degradation dict on failure.
        """
        if not self.available:
            return self._degraded(
                f"Medical Agent unavailable (import failed: {self._import_error})"
            )

        try:
            # --- Input normalisation ---
            if extraction is None:
                extraction = self._build_extraction(**kwargs)
            elif isinstance(extraction, dict):
                extraction = self._ExtractionResponse.model_validate(extraction)
            # else: already an ExtractionResponse — pass through

            return self._run_async(extraction)

        except Exception as exc:  # pylint: disable=broad-except
            return self._degraded(f"Medical Agent execution error: {exc}")


class HealthcareOrchestrator:
    """
    Central AI Clinical Agent orchestrating EHR, Clinical Guidelines, and Notification MCP servers.

    Methods:
    - process_telemetry(): Evaluate wearable vital signs across all MCP servers.
    - evaluate_prescription(): Delegate to Medical Agent, synthesise risk, enrich with EHR
      context, and log audit trail to Notification MCP.
    - doctor_decision(): Execute human clinician CONFIRM / REJECT gate.
    """

    def __init__(self, api_token: str = DEFAULT_TOKEN):
        self.api_token = api_token
        self.ehr = _ehr
        self.clinical = _clinical
        self.notification = _notification
        self.medical_agent = MedicalAgentAdapter()

    def detect_anomalies(self, vitals: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect clinical anomalies from vital signs stream."""
        anomalies = []
        hr = vitals.get("heart_rate") or vitals.get("hr")
        spo2 = vitals.get("spo2") or vitals.get("oxygen_saturation")
        sbp = vitals.get("systolic_bp") or vitals.get("sbp")
        dbp = vitals.get("diastolic_bp") or vitals.get("dbp")

        if spo2 is not None and spo2 < 90:
            anomalies.append({
                "code": "LOW_SPO2",
                "parameter": "SpO2",
                "value": spo2,
                "threshold": 90,
                "severity": "CRITICAL" if spo2 < 88 else "HIGH",
                "finding": f"Low oxygen saturation: {spo2}% (Normal: >=95%)"
            })
        if hr is not None and hr > 100:
            anomalies.append({
                "code": "HIGH_HR",
                "parameter": "Heart Rate",
                "value": hr,
                "threshold": 100,
                "severity": "CRITICAL" if hr > 120 else "HIGH",
                "finding": f"Tachycardia: {hr} bpm (Normal: 60-100 bpm)"
            })
        if hr is not None and hr < 50:
            anomalies.append({
                "code": "LOW_HR",
                "parameter": "Heart Rate",
                "value": hr,
                "threshold": 50,
                "severity": "HIGH",
                "finding": f"Bradycardia: {hr} bpm (Normal: 60-100 bpm)"
            })
        if sbp is not None and sbp >= 180:
            anomalies.append({
                "code": "HIGH_BP",
                "parameter": "Systolic Blood Pressure",
                "value": sbp,
                "threshold": 180,
                "severity": "CRITICAL",
                "finding": f"Hypertensive crisis: {sbp} mmHg (Threshold: >=180 mmHg)"
            })

        return anomalies

    def process_telemetry(self, patient_id: str, vitals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate wearable vitals for a patient through coordinated MCP calls.

        Steps:
        1. Anomaly Detection
        2. Query EHR-MCP (Conditions, Allergies, Prescriptions, Emergency Contact)
        3. Query Clinical-MCP (Guidelines for anomalies + Drug-drug interactions)
        4. Multi-Factor Risk Assessment
        5. Query Notification-MCP (Log audit trail in PENDING_CONFIRMATION status)
        """
        anomalies = self.detect_anomalies(vitals)
        if not anomalies:
            return {
                "patient_id": patient_id,
                "risk_level": "NORMAL",
                "status": "STABLE",
                "message": "All vital parameters within normal clinical thresholds.",
                "anomalies": []
            }

        # Step 1: Query EHR-MCP
        profile = self.ehr.patient_profile(patient_id)
        if profile.get("error"):
            return {
                "error": True,
                "code": "EHR_FETCH_FAILED",
                "message": profile.get("message", "Failed to retrieve patient profile.")
            }

        prescriptions_res = self.ehr.fetch_active_prescriptions(patient_id, self.api_token)
        active_rx = prescriptions_res.get("prescriptions", [])
        med_names = [rx["drug"] for rx in active_rx if "drug" in rx]

        contact_res = self.ehr.get_emergency_contact(patient_id, self.api_token)
        emergency_contact = contact_res.get("emergency_contact") or {}
        contact_phone = emergency_contact.get("phone", "")

        # Step 2: Query Clinical-MCP for each anomaly
        guidelines_applied = []
        for anomaly in anomalies:
            guide = self.clinical.search_clinical_guidance(anomaly["code"])
            if guide.get("found"):
                guidelines_applied.append({
                    "code": anomaly["code"],
                    "observation": guide.get("observation"),
                    "recommended_action": guide.get("recommended_action")
                })

        # Query Clinical-MCP for drug interactions
        interactions_found = []
        if len(med_names) >= 2:
            interaction_res = self.clinical.query_drug_interactions(med_names)
            if interaction_res.get("interaction_found"):
                interactions_found = interaction_res.get("interactions", [])

        # Step 3: Multi-Factor Risk Assessment
        has_critical_anomaly = any(a["severity"] == "CRITICAL" for a in anomalies)
        has_high_drug_interaction = any(i.get("severity") == "high" for i in interactions_found)
        conditions = profile.get("conditions", [])

        # Assess risk
        if has_critical_anomaly or (has_high_drug_interaction and len(anomalies) > 0):
            overall_risk = "CRITICAL"
        elif len(anomalies) >= 2 or has_high_drug_interaction:
            overall_risk = "HIGH"
        else:
            overall_risk = "MODERATE"

        # Step 4: Call Notification-MCP to record audit trail
        finding_summaries = [a["finding"] for a in anomalies]
        event_message = (
            f"Vitals Anomaly: {', '.join(finding_summaries)}. "
            f"Conditions: {', '.join(conditions) if conditions else 'None'}. "
            f"Active Meds: {', '.join(med_names) if med_names else 'None'}."
        )

        audit_event = self.notification.log_audit_trail(
            patient_id=patient_id,
            event_type="CLINICAL_ESCALATION",
            risk_level=overall_risk,
            message=event_message,
            phone=contact_phone,
            event_state={
                "risk": overall_risk,
                "anomalies": anomalies,
                "conditions": conditions,
                "medications": med_names,
                "phone": contact_phone
            }
        )

        return {
            "patient_id": patient_id,
            "patient_name": profile.get("name"),
            "risk_level": overall_risk,
            "event_id": audit_event.get("event_id"),
            "status": "PENDING_CONFIRMATION",
            "requires_human_confirmation": True,
            "vitals": vitals,
            "anomalies": anomalies,
            "patient_context": {
                "age": profile.get("age"),
                "gender": profile.get("gender"),
                "conditions": conditions,
                "allergies": profile.get("allergies", []),
                "active_prescriptions": med_names,
                "emergency_contact": emergency_contact
            },
            "clinical_guidelines": guidelines_applied,
            "drug_interactions": interactions_found,
            "escalation_message": event_message
        }

    def evaluate_prescription(
        self,
        extraction: Any,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a prescription through the Medical & Pharmaceutical Agent and
        synthesise a unified risk assessment.

        Steps:
        1. Delegate to MedicalAgentAdapter.run(extraction) → AnalysisResponse.
        2. Map AnalysisResponse.status → risk_level and human_review_required.
        3. If patient_id supplied: enrich result with EHR patient context.
        4. If risk_level in ("CRITICAL", "HIGH"): log audit trail to Notification MCP.
        5. Return unified assessment dict.

        Safety Invariants preserved:
        - approved is ALWAYS False — no prescription is auto-approved.
        - human_review_required is ALWAYS True for all statuses.
        - INFORMATIONAL does NOT mean safe-to-dispense (Safety Invariant #3).

        Args:
            extraction: ExtractionResponse, dict, or keyword args understood by
                        MedicalAgentAdapter.run().
            patient_id: Optional patient identifier for EHR context enrichment.

        Returns:
            Unified assessment dict with risk_level, status, approved, event_id, etc.
        """
        # Step 1: Invoke Medical Agent
        analysis = self.medical_agent.run(extraction)

        # Normalise to plain dict (AnalysisResponse is a Pydantic model)
        if hasattr(analysis, "model_dump"):
            analysis_dict = analysis.model_dump()
        elif isinstance(analysis, dict):
            analysis_dict = analysis
        else:
            analysis_dict = dict(analysis)

        # Step 2: Status → risk_level mapping
        ma_status = analysis_dict.get("status", "INSUFFICIENT_INFORMATION")
        _STATUS_MAP: Dict[str, tuple] = {
            "CRITICAL_REVIEW_REQUIRED": ("CRITICAL", True),
            "REVIEW_REQUIRED":          ("HIGH",     True),
            "INSUFFICIENT_INFORMATION": ("HIGH",     True),
            "INFORMATIONAL":            ("MODERATE", True),  # Safety Invariant #3: never auto-approved
        }
        risk_level, requires_human_confirmation = _STATUS_MAP.get(
            ma_status, ("HIGH", True)
        )

        prescription_id = analysis_dict.get("prescription_id", "UNKNOWN")

        # Step 3: Optional EHR context enrichment
        patient_context: Dict[str, Any] = {}
        if patient_id:
            try:
                profile = self.ehr.patient_profile(patient_id)
                if not profile.get("error"):
                    patient_context["name"] = profile.get("name")
                    patient_context["age"] = profile.get("age")
                    patient_context["gender"] = profile.get("gender")
                    patient_context["conditions"] = profile.get("conditions", [])
                    patient_context["ehr_allergies"] = profile.get("allergies", [])
            except Exception:  # pylint: disable=broad-except
                pass  # EHR unavailable — degrade gracefully; don't fail prescription eval

            try:
                allergy_res = self.ehr.get_allergies(patient_id, self.api_token)
                if not allergy_res.get("error"):
                    patient_context["allergies"] = allergy_res.get("allergies", [])
            except Exception:  # pylint: disable=broad-except
                pass

        # Step 4: Audit trail for CRITICAL / HIGH risk
        event_id: Optional[str] = None
        if risk_level in ("CRITICAL", "HIGH"):
            try:
                issues_summary = "; ".join(analysis_dict.get("issues", [])) or "No issues listed"
                audit_event = self.notification.log_audit_trail(
                    patient_id=patient_id or "UNKNOWN",
                    event_type="PRESCRIPTION_REVIEW",
                    risk_level=risk_level,
                    message=(
                        f"Prescription {prescription_id} requires {risk_level} review. "
                        f"Status: {ma_status}. Issues: {issues_summary}"
                    ),
                    phone="",
                    event_state={
                        "risk": risk_level,
                        "prescription_id": prescription_id,
                        "status": ma_status,
                        "issues": analysis_dict.get("issues", []),
                        "drug_interactions": analysis_dict.get("drug_interactions", {}),
                    },
                )
                event_id = audit_event.get("event_id")
            except Exception:  # pylint: disable=broad-except
                pass  # Notification MCP unavailable — degrade gracefully

        # Step 5: Return unified assessment
        return {
            "patient_id": patient_id,
            "prescription_id": prescription_id,
            "risk_level": risk_level,
            "status": "PENDING_CONFIRMATION",
            "approved": False,                        # Safety Invariant #3
            "human_review_required": True,            # Always True
            "requires_human_confirmation": requires_human_confirmation,
            "medical_analysis": analysis_dict,
            "issues": analysis_dict.get("issues", []),
            "drug_interactions": analysis_dict.get("drug_interactions", {}),
            "patient_context": patient_context,
            "event_id": event_id,
        }

    def doctor_decision(
        self,
        event_id: str,
        action: str,
        doctor_name: str,
        phone: str = "",
        reason: str = ""
    ) -> Dict[str, Any]:
        """
        Execute human clinician confirmation or rejection gate.

        If action == 'CONFIRM':
          1. Mints 5-minute single-use token via confirm_escalation().
          2. Dispatches emergency SMS to bound phone via trigger_emergency_sms().
          3. Transitions event status to 'DISPATCHED'.

        If action == 'REJECT':
          1. Declines escalation via reject_escalation().
          2. Transitions event status to 'REJECTED'.
        """
        clean_action = action.strip().upper()

        if clean_action == "CONFIRM":
            # Phase A: Clinician Confirmation
            conf = self.notification.confirm_escalation(
                event_id=event_id,
                confirmed_by=doctor_name,
                phone=phone
            )
            if not conf.get("success"):
                return {
                    "success": False,
                    "action": "CONFIRM",
                    "error": conf.get("message", "Confirmation failed.")
                }

            token = conf["confirmation_token"]
            bound_phone = conf["bound_phone"]
            patient_id = conf["patient_id"]

            # Phase B: Emergency SMS Dispatch
            sms_body = (
                f"CLINICAL EMERGENCY ALERT: Dr. {doctor_name} has escalated care for Patient {patient_id}. "
                f"Immediate clinical action requested. Please contact triage."
            )
            dispatch = self.notification.trigger_emergency_sms(
                patient_id=patient_id,
                phone=bound_phone,
                message=sms_body,
                confirmation_token=token,
                event_id=event_id
            )

            return {
                "success": dispatch.get("success", False),
                "action": "CONFIRM",
                "event_id": event_id,
                "status": dispatch.get("status"),
                "patient_id": patient_id,
                "phone": bound_phone,
                "dispatch_id": dispatch.get("dispatch_id"),
                "token_expires_at": conf.get("expires_at"),
                "message": dispatch.get("message")
            }

        elif clean_action == "REJECT":
            rej = self.notification.reject_escalation(
                event_id=event_id,
                rejected_by=doctor_name,
                reason=reason
            )
            return {
                "success": rej.get("success", False),
                "action": "REJECT",
                "event_id": event_id,
                "status": "REJECTED",
                "rejected_by": doctor_name,
                "reason": reason or "No clinical justification provided."
            }
        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Expected 'CONFIRM' or 'REJECT'."
            }


def run_demo():
    """Run the complete end-to-end clinical demonstration scenario from the specification."""
    print("=" * 75)
    print("  HEALTHCARE AI ORCHESTRATOR: COMPLETE END-TO-END DEMO SCENARIO")
    print("=" * 75)

    orchestrator = HealthcareOrchestrator()

    # Scenario: Wearable sensor detects sudden telemetry spike for Patient P001
    print("\n[SCENARIO] Wearable Sensor Event Detected for Patient P001:")
    incoming_vitals = {
        "heart_rate": 128,
        "spo2": 87,
        "systolic_bp": 142,
        "diastolic_bp": 92
    }
    print(f"  - Heart Rate: {incoming_vitals['heart_rate']} bpm")
    print(f"  - SpO2:       {incoming_vitals['spo2']}%")
    print(f"  - BP:         {incoming_vitals['systolic_bp']}/{incoming_vitals['diastolic_bp']} mmHg")

    # Step 1: Orchestrator evaluates telemetry across all 3 MCP servers
    print("\n[STEP 1] Orchestrator Evaluating Telemetry across MCP Ecosystem...")
    result = orchestrator.process_telemetry("P001", incoming_vitals)

    print(f"  -> Patient:          {result['patient_name']} (ID: {result['patient_id']})")
    print(f"  -> Assessed Risk:    {result['risk_level']}")
    print(f"  -> Audit Event:      {result['event_id']}")
    print(f"  -> Lifecycle Status: {result['status']}")

    print("\n  [EHR-MCP Context Retrieved]")
    print(f"  - Diagnosed Conditions: {result['patient_context']['conditions']}")
    print(f"  - Active Medications:   {result['patient_context']['active_prescriptions']}")
    print(f"  - Documented Allergies: {result['patient_context']['allergies']}")
    print(f"  - Emergency Contact:    {result['patient_context']['emergency_contact']['name']} ({result['patient_context']['emergency_contact']['phone']})")

    print("\n  [Clinical-MCP Evidence Retrieved]")
    for g in result["clinical_guidelines"]:
        print(f"  - Guideline [{g['code']}]: {g['observation']}")
        print(f"    Action: {g['recommended_action']}")

    # Step 2: Clinician Dashboard Simulation
    print("\n" + "-" * 75)
    print("  [CLINICAL DASHBOARD MOCKUP]")
    print(f"  [!] {result['risk_level']} ALERT: Patient {result['patient_id']} ({result['patient_name']})")
    print(f"  SpO2: {incoming_vitals['spo2']}% | Heart Rate: {incoming_vitals['heart_rate']} bpm")
    print(f"  EHR Comorbidities: {result['patient_context']['conditions']}")
    print(f"  Pending Event ID: {result['event_id']}")
    print("  Human Clinician Action: [ CONFIRM ] or [ REJECT ]")
    print("-" * 75)

    # Step 3: Attending Physician reviews and CONFIRMS escalation
    print("\n[STEP 2] Attending Physician Reviews and Clicks [ CONFIRM ]...")
    doctor_name = "Dr. Gregory House, MD"
    decision = orchestrator.doctor_decision(
        event_id=result["event_id"],
        action="CONFIRM",
        doctor_name=doctor_name,
        phone=result["patient_context"]["emergency_contact"]["phone"]
    )

    print(f"  -> Clinician Action:     CONFIRM (by {doctor_name})")
    print(f"  -> SMS Dispatch Status:  {decision['status']}")
    print(f"  -> Carrier Message ID:   {decision['dispatch_id']}")
    print(f"  -> Recipient Phone:      {decision['phone']}")
    print(f"  -> Token Expiration:     {decision['token_expires_at']}")

    # Step 4: Verify Final Audit Trail via Notification-MCP
    print("\n[STEP 3] Inspecting Final Audit Trail Record...")
    trail = orchestrator.notification.get_audit_trail(result["event_id"])
    evt = trail["audit_event"]
    print(f"  - Event ID:      {evt['event_id']}")
    print(f"  - Status:        {evt['status']}")
    print(f"  - Confirmed By:  {evt['confirmed_by']}")
    print(f"  - Dispatched At: {evt['dispatched_at']}")

    print("\n" + "=" * 75)
    print("  END-TO-END HEALTHCARE ORCHESTRATION DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_demo()

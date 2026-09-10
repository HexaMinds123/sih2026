"""
Healthcare AI Orchestrator Agent

Coordinates the three independent MCP servers:
1. EHR-MCP: Retrieves patient medical context (demographics, conditions, prescriptions).
2. Clinical-MCP: Retrieves evidence-based clinical guidelines and drug interaction matrices.
3. Notification-MCP: Handles audit logging, human confirmation gates, and SMS dispatches.

Additionally integrates the downstream Medical & Pharmaceutical Agent:
4. Medical Agent: Deterministic prescription analysis via ClinicalMCPClient (stdio transport).
   Receives ExtractionResponse, returns AnalysisResponse. Never an orchestrator.

SAFETY ARCHITECTURE:
- Risk evaluation is performed here in the Orchestrator.
- Notification-MCP never decides if an emergency exists.
- Real-world external communication is blocked until an attending clinician explicitly confirms.
- INFORMATIONAL status from the Medical Agent is NEVER interpreted as approved or safe.
  All prescription analyses require explicit human clinician confirmation.
- If the Medical Agent is unavailable, the Orchestrator degrades gracefully:
  available=False, status=INSUFFICIENT_INFORMATION, human_review_required=True.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Medical Agent Adapter
# ---------------------------------------------------------------------------

def _import_medical_agent():
    """
    Safely resolve and import the prescription-system Medical Agent module.

    Adds prescription-system/ to sys.path so ``app`` is a resolvable package,
    then imports ``app.medical_agent.analyze_prescription`` and the
    ``app.models.ExtractionResponse`` / ``AnalysisResponse`` classes.

    Returns a tuple (analyze_fn, ExtractionResponse, AnalysisResponse)
    or raises ImportError with a descriptive message if unavailable.
    """
    import importlib

    rx_system_root = ROOT / "prescription-system"
    pkg_str = str(rx_system_root)
    if pkg_str not in sys.path:
        sys.path.insert(0, pkg_str)

    try:
        ma = importlib.import_module("app.medical_agent")
        models = importlib.import_module("app.models")
        return (
            ma.analyze_prescription,
            models.ExtractionResponse,
            models.AnalysisResponse,
        )
    except Exception as exc:
        raise ImportError(
            f"Cannot import Medical & Pharmaceutical Agent: {exc}"
        ) from exc


class MedicalAgentAdapter:
    """Adapter that bridges the async Medical & Pharmaceutical Agent with the
    synchronous HealthcareOrchestrator.

    Responsibilities
    ----------------
    - **Safe import**: degrades gracefully if the prescription-system package is
      missing or any dependency is unavailable.
    - **Input normalization**: accepts ``ExtractionResponse`` instances or dicts.
    - **Sync/async bridge**: executes the async ``analyze_prescription`` coroutine
      safely regardless of whether an event loop is already running.
    - **Error isolation**: any failure returns a structured degradation dict so
      the Orchestrator never crashes and never fabricates clinical evidence.

    SAFETY INVARIANTS
    -----------------
    - ``human_review_required`` is always ``True`` — even on failure.
    - ``approved`` is always ``False`` — approval is the clinician's gate.
    - ``available: False`` is set explicitly on any import or runtime failure.
    """

    # Status strings produced by the Medical Agent
    _CRITICAL = "CRITICAL_REVIEW_REQUIRED"
    _REVIEW = "REVIEW_REQUIRED"
    _INSUFFICIENT = "INSUFFICIENT_INFORMATION"
    _INFORMATIONAL = "INFORMATIONAL"

    # Map Medical Agent status → Orchestrator risk level
    # Safety Invariant: INFORMATIONAL maps to MODERATE, not safe/approved.
    _RISK_MAP: Dict[str, str] = {
        _CRITICAL: "CRITICAL",
        _REVIEW: "HIGH",
        _INSUFFICIENT: "HIGH",
        _INFORMATIONAL: "MODERATE",
    }

    def __init__(self) -> None:
        self._available: Optional[bool] = None  # lazily determined on first call
        self._analyze_fn = None
        self._ExtractionResponse = None
        self._AnalysisResponse = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> bool:
        """Try to import the Medical Agent on first use. Returns True if available."""
        if self._available is not None:
            return self._available
        try:
            (
                self._analyze_fn,
                self._ExtractionResponse,
                self._AnalysisResponse,
            ) = _import_medical_agent()
            self._available = True
        except ImportError as exc:
            logger.warning("MedicalAgentAdapter: import failed — %s", exc)
            self._available = False
        return self._available

    @staticmethod
    def _run_coroutine(coro) -> Any:
        """Execute an asyncio coroutine from synchronous code.

        Compatible with both standalone scripts (no running loop) and
        environments with a running event loop (e.g. pytest-asyncio, FastAPI,
        Jupyter) by delegating to a separate thread in the latter case.
        """
        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False

        if not running:
            return asyncio.run(coro)

        # A loop is already running — spin up a thread so we don't block it.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=120)

    def _to_extraction(self, extraction: Any, prescription_id: str = "RX-ORCHESTRATOR") -> Any:
        """Normalize input to an ExtractionResponse instance.

        Accepts:
        - An existing ``ExtractionResponse`` object (pass-through).
        - A dict validated via Pydantic ``model_validate``.
        """
        if isinstance(extraction, self._ExtractionResponse):
            return extraction
        if isinstance(extraction, dict):
            return self._ExtractionResponse.model_validate({
                "prescription_id": extraction.get("prescription_id", prescription_id),
                "ocr": extraction.get("ocr", {
                    "raw_text": extraction.get("raw_text", ""),
                    "human_verification_required": extraction.get(
                        "human_verification_required", True
                    ),
                }),
                "prescription": extraction.get("prescription", {
                    "patient": extraction.get("patient", {}),
                    "medications": extraction.get("medications", []),
                    "condition": extraction.get("condition"),
                }),
                "human_verification_required": extraction.get(
                    "human_verification_required", True
                ),
            })
        raise TypeError(
            f"extraction must be ExtractionResponse or dict, got {type(extraction).__name__!r}"
        )

    @staticmethod
    def _build_degraded_response(
        prescription_id: str,
        error_msg: str,
    ) -> Dict[str, Any]:
        """Return a structured failure dict the Orchestrator can safely consume."""
        return {
            "available": False,
            "prescription_id": prescription_id,
            "status": "INSUFFICIENT_INFORMATION",
            "risk_level": "HIGH",
            "human_review_required": True,
            "approved": False,
            "medications": [],
            "drug_interactions": {"interaction_found": False, "interactions": []},
            "issues": [error_msg],
            "audit": {"tools_called": []},
            "error": error_msg,
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, extraction: Any, prescription_id: str = "RX-ORCHESTRATOR") -> Dict[str, Any]:
        """Run the Medical & Pharmaceutical Agent on a prescription extraction.

        Parameters
        ----------
        extraction:
            Either an ``ExtractionResponse`` instance or a dict following that
            schema (e.g., built by the Orchestrator from OCR output).
        prescription_id:
            Fallback ID used when the extraction dict carries none.

        Returns
        -------
        dict with keys:
            available             bool  — False if the Medical Agent could not run
            prescription_id       str
            status                str   — CRITICAL_REVIEW_REQUIRED | REVIEW_REQUIRED |
                                          INSUFFICIENT_INFORMATION | INFORMATIONAL
            risk_level            str   — CRITICAL | HIGH | MODERATE
            human_review_required bool  — always True (safety invariant)
            approved              bool  — always False (clinician gate)
            medications           list
            drug_interactions     dict
            issues                list[str]
            audit                 dict
            error                 str | None
        """
        pid = prescription_id

        if not self._ensure_loaded():
            return self._build_degraded_response(
                pid, "Medical & Pharmaceutical Agent unavailable (import failed)"
            )

        try:
            extraction_obj = self._to_extraction(extraction, prescription_id=pid)
            pid = extraction_obj.prescription_id
            result = self._run_coroutine(self._analyze_fn(extraction_obj))
        except Exception as exc:
            return self._build_degraded_response(
                pid, f"Medical & Pharmaceutical Agent error: {exc}"
            )

        # Serialize Pydantic model to dict for uniform downstream handling
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump()
        elif hasattr(result, "dict"):
            result_dict = result.dict()
        else:
            result_dict = dict(result)

        status = result_dict.get("status", self._INSUFFICIENT)
        risk_level = self._RISK_MAP.get(status, "HIGH")

        return {
            "available": True,
            "prescription_id": result_dict.get("prescription_id", pid),
            "status": status,
            "risk_level": risk_level,
            # SAFETY: human_review_required is ALWAYS True — never auto-approve
            "human_review_required": True,
            # SAFETY: approved is ALWAYS False — clinician must confirm
            "approved": False,
            "medications": result_dict.get("medications", []),
            "drug_interactions": result_dict.get("drug_interactions", {}),
            "issues": result_dict.get("issues", []),
            "audit": result_dict.get("audit", {"tools_called": []}),
            "error": None,
        }


class HealthcareOrchestrator:
    """Central AI Clinical Agent orchestrating EHR, Clinical Guidelines,
    Notification MCP servers, and the Medical & Pharmaceutical Agent.

    Architecture
    ------------
    This class is the central reasoning layer. Downstream agents and MCP
    servers are *called by* this class and return structured results. They
    never become the master controller.

    Medical & Pharma Agent
    ----------------------
    Connected via ``MedicalAgentAdapter``. Invoked through
    ``evaluate_prescription()`` which synthesises its ``AnalysisResponse``
    into the standard Orchestrator risk format.
    """

    def __init__(self, api_token: str = DEFAULT_TOKEN):
        self.api_token = api_token
        self.ehr = _ehr
        self.clinical = _clinical
        self.notification = _notification
        # Medical & Pharmaceutical Agent adapter (downstream specialization)
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

    # =========================================================================
    # Phase 7 — Medical & Pharmaceutical Agent integration
    # =========================================================================

    def evaluate_prescription(
        self,
        extraction: Any,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Orchestrate a prescription analysis through the Medical & Pharma Agent.

        This is the Orchestrator-side entry point for prescription evaluation.
        It:
        1. Invokes the Medical & Pharmaceutical Agent (via MedicalAgentAdapter).
        2. Optionally enriches the result with EHR patient context when a
           ``patient_id`` is supplied (allergies, chronic conditions).
        3. Synthesises the agent's structured ``AnalysisResponse`` into the
           Orchestrator's standard risk / status format.
        4. Logs a PENDING_CONFIRMATION audit event to Notification-MCP when
           risk is CRITICAL or HIGH, preserving the human-in-the-loop gate.

        SAFETY INVARIANTS (enforced regardless of Medical Agent output)
        ---------------------------------------------------------------
        - ``human_review_required`` is ALWAYS ``True``.
        - ``approved`` is ALWAYS ``False`` — no prescription is ever
          auto-approved by the Orchestrator.
        - ``INFORMATIONAL`` status maps to ``MODERATE`` risk, NOT to safe.
        - If the Medical Agent is unavailable or raises an exception the result
          degrades to ``INSUFFICIENT_INFORMATION`` / ``HIGH`` risk — the
          Orchestrator never crashes and never fabricates clinical evidence.

        Parameters
        ----------
        extraction:
            An ``ExtractionResponse`` instance or a compatible dict describing
            the parsed prescription (prescription_id, medications, condition,
            ocr metadata).
        patient_id:
            Optional EHR patient ID. When supplied, the Orchestrator fetches
            the patient's known allergies and conditions from EHR-MCP and
            includes them in the returned context.

        Returns
        -------
        dict with keys:
            prescription_id           str
            patient_id                str | None
            risk_level                str   — CRITICAL | HIGH | MODERATE
            status                    str   — mirrors AnalysisResponse.status
            approved                  bool  — always False
            human_review_required     bool  — always True
            requires_human_confirmation bool — always True (alias for downstream compat)
            medical_analysis          dict  — full Medical Agent result payload
            patient_context           dict | None — EHR context if patient_id supplied
            event_id                  str | None  — Notification-MCP audit event ID
            issues                    list[str]
            drug_interactions         dict
        """
        # -----------------------------------------------------------------------
        # Step 1 — Run Medical & Pharmaceutical Agent
        # -----------------------------------------------------------------------
        medical_result = self.medical_agent.run(extraction)

        agent_status: str = medical_result.get("status", "INSUFFICIENT_INFORMATION")
        prescription_id: str = medical_result.get("prescription_id", "")
        risk_level: str = medical_result.get("risk_level", "HIGH")

        # -----------------------------------------------------------------------
        # Step 2 — Optional EHR enrichment
        # -----------------------------------------------------------------------
        patient_context: Optional[Dict[str, Any]] = None
        if patient_id:
            try:
                profile = self.ehr.patient_profile(patient_id)
                if not profile.get("error"):
                    allergies_res = self.ehr.get_allergies(patient_id, self.api_token)
                    conditions_res = self.ehr.get_medical_conditions(patient_id, self.api_token)
                    patient_context = {
                        "patient_id": patient_id,
                        "name": profile.get("name"),
                        "age": profile.get("age"),
                        "gender": profile.get("gender"),
                        "allergies": allergies_res.get("allergies", profile.get("allergies", [])),
                        "conditions": conditions_res.get("conditions", profile.get("conditions", [])),
                    }
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "evaluate_prescription: EHR enrichment failed for %s — %s",
                    patient_id, exc
                )

        # -----------------------------------------------------------------------
        # Step 3 — Build combined issues list
        # -----------------------------------------------------------------------
        issues: List[str] = list(medical_result.get("issues", []))
        if not medical_result.get("available", True):
            err = medical_result.get("error", "Medical Agent unavailable")
            if err and err not in issues:
                issues.insert(0, err)

        # -----------------------------------------------------------------------
        # Step 4 — Log audit trail when risk warrants human gate
        # -----------------------------------------------------------------------
        event_id: Optional[str] = None
        if risk_level in ("CRITICAL", "HIGH"):
            try:
                issue_summary = (
                    "; ".join(issues[:3]) if issues
                    else f"Prescription risk: {agent_status}"
                )
                audit_event = self.notification.log_audit_trail(
                    patient_id=patient_id or "UNKNOWN",
                    event_type="PRESCRIPTION_REVIEW_REQUIRED",
                    risk_level=risk_level,
                    message=(
                        f"Medical Agent [{agent_status}]: {issue_summary}. "
                        f"Prescription ID: {prescription_id}."
                    ),
                    phone="",
                    event_state={
                        "risk": risk_level,
                        "reason": agent_status,
                        "prescription_id": prescription_id,
                        "patient_id": patient_id or "UNKNOWN",
                    },
                )
                event_id = audit_event.get("event_id")
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "evaluate_prescription: Notification MCP audit failed — %s", exc
                )

        # -----------------------------------------------------------------------
        # Step 5 — Assemble unified result
        # Safety Invariants enforced here — these fields are NEVER overridden by
        # Medical Agent output regardless of status.
        # -----------------------------------------------------------------------
        return {
            "prescription_id": prescription_id,
            "patient_id": patient_id,
            "risk_level": risk_level,
            "status": agent_status,
            "approved": False,                     # Invariant: never auto-approved
            "human_review_required": True,         # Invariant: always required
            "requires_human_confirmation": True,   # Alias for downstream compat
            "medical_analysis": medical_result,
            "patient_context": patient_context,
            "event_id": event_id,
            "issues": issues,
            "drug_interactions": medical_result.get("drug_interactions", {}),
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

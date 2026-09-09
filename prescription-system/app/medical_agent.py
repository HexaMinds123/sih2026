"""Deterministic prescription analysis through the existing MCP client."""

from __future__ import annotations

from typing import Any, Protocol

from .mcp_client import ClinicalMCPClient, ClinicalMCPError
from .models import (
	AnalysisResponse,
	AuditCall,
	EvidenceItem,
	ExtractionResponse,
	MedicationAnalysis,
)


class MCPClient(Protocol):
	async def connect(self) -> list[str]: ...
	async def close(self) -> None: ...
	async def query_drug_interactions(self, medications: list[str]) -> dict[str, Any]: ...
	async def search_prescription_guidance(self, medication: str, condition: str | None = None, dosage: str | None = None) -> dict[str, Any]: ...


def _dosage_text(medication: Any) -> str | None:
	parts = [medication.strength, medication.dose, medication.frequency]
	value = " ".join(part.strip() for part in parts if part and part.strip())
	return value or None


def _evidence_items(result: dict[str, Any]) -> list[EvidenceItem]:
	items = result.get("evidence")
	if not isinstance(items, list):
		raise ClinicalMCPError("MCP guidance response has malformed evidence")
	return [EvidenceItem(
		text=item.get("text"),
		source=item.get("source"),
		document_id=item.get("document_id"),
		section=item.get("section"),
		page=item.get("page"),
		version=item.get("version"),
		jurisdiction=item.get("jurisdiction"),
		publication_date=item.get("publication_date"),
		source_url=item.get("source_url"),
		retrieval_similarity_score=item.get("similarity_score"),
	) for item in items if isinstance(item, dict)]


async def analyze_prescription(
	extraction: ExtractionResponse,
	client: MCPClient | None = None,
) -> AnalysisResponse:
	prescription = extraction.prescription
	issues: list[str] = []
	audit_calls: list[AuditCall] = []
	medication_records = prescription.medications

	if not medication_records:
		issues.append("No medication was extracted from the prescription")
	if prescription.uncertain_medications:
		issues.append("One or more medication names are uncertain")
	if extraction.ocr.human_verification_required:
		issues.append("OCR quality requires human verification")
	if prescription.warnings:
		issues.extend(warning.reason for warning in prescription.warnings)

	for medication in medication_records:
		if not medication.name.strip():
			issues.append("A medication name is missing")
		if not medication.strength and not medication.dose:
			issues.append(f"Dosage is missing for {medication.name}")
		if not medication.frequency:
			issues.append(f"Frequency is missing for {medication.name}")
	if not prescription.condition:
		issues.append("Prescription condition is missing")

	analysis_medications: list[MedicationAnalysis] = []
	interaction_result: dict[str, Any] = {
		"interaction_found": False,
		"drugs": [medication.name for medication in medication_records if medication.name.strip()],
		"interactions": [],
	}
	if client is None:
		client = ClinicalMCPClient()
		owns_client = True
	else:
		owns_client = False

	try:
		await client.connect()
		medication_names = [medication.name for medication in medication_records if medication.name.strip()]
		if len(medication_names) >= 2:
			interaction_arguments = {"meds_list": medication_names}
			try:
				interaction_result = await client.query_drug_interactions(medication_names)
				audit_calls.append(AuditCall(tool="query_drug_interactions", arguments=interaction_arguments, result_received=True))
			except Exception:
				audit_calls.append(AuditCall(tool="query_drug_interactions", arguments=interaction_arguments, result_received=False))
				raise
		for medication in medication_records:
			dosage = _dosage_text(medication)
			arguments = {"medication": medication.name, "condition": prescription.condition, "dosage": dosage}
			try:
				guidance = await client.search_prescription_guidance(medication.name, prescription.condition, dosage)
				if not isinstance(guidance, dict):
					raise ClinicalMCPError("MCP guidance response is not an object")
				evidence = _evidence_items(guidance)
				analysis_medications.append(MedicationAnalysis(
					medication=medication.name,
					condition=prescription.condition,
					dosage=dosage,
					evidence_status="EVIDENCE_FOUND" if guidance.get("evidence_found") and evidence else "NO_RELEVANT_EVIDENCE",
					evidence=evidence,
				))
				audit_calls.append(AuditCall(tool="search_prescription_guidance", arguments=arguments, result_received=True))
			except Exception:
				audit_calls.append(AuditCall(tool="search_prescription_guidance", arguments=arguments, result_received=False))
				raise
	except Exception as error:
		issues.append(f"Clinical knowledge service unavailable: {error}")
		return AnalysisResponse(
			prescription_id=extraction.prescription_id,
			status="INSUFFICIENT_INFORMATION",
			human_review_required=True,
			medications=analysis_medications,
			drug_interactions=interaction_result,
			issues=issues,
			audit={"tools_called": audit_calls},
		)
	finally:
		if owns_client:
			try:
				await client.close()
			except Exception:
				pass

	high_severity = any(
		isinstance(item, dict) and str(item.get("severity", "")).lower() == "high"
		for item in interaction_result.get("interactions", [])
	)
	if high_severity:
		status = "CRITICAL_REVIEW_REQUIRED"
	elif not medication_records or any(item.evidence_status == "NO_RELEVANT_EVIDENCE" for item in analysis_medications):
		status = "INSUFFICIENT_INFORMATION"
	elif issues:
		status = "REVIEW_REQUIRED"
	else:
		status = "INFORMATIONAL"

	return AnalysisResponse(
		prescription_id=extraction.prescription_id,
		status=status,
		human_review_required=status != "INFORMATIONAL",
		medications=analysis_medications,
		drug_interactions=interaction_result,
		issues=issues,
		audit={"tools_called": audit_calls},
	)

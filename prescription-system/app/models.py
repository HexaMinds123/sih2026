"""Validated models for prescription ingestion and extraction."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ParserWarning(BaseModel):
	text: str
	reason: str


class Patient(BaseModel):
	name: str | None = None
	age: int | None = Field(default=None, ge=0, le=150)
	gender: str | None = None


class Medication(BaseModel):
	name: str
	strength: str | None = None
	dose: str | None = None
	frequency: str | None = None
	route: str | None = None
	duration: str | None = None
	instructions: str | None = None


class Prescription(BaseModel):
	model_config = ConfigDict(extra="forbid")

	patient: Patient
	prescription_date: date | None = None
	condition: str | None = None
	medications: list[Medication] = Field(default_factory=list)
	uncertain_medications: list[ParserWarning] = Field(default_factory=list)
	warnings: list[ParserWarning] = Field(default_factory=list)


class OCRResult(BaseModel):
	raw_text: str
	ocr_confidence: float | None = Field(default=None, ge=0, le=1)
	warnings: list[str] = Field(default_factory=list)
	human_verification_required: bool = False


class UploadResponse(BaseModel):
	prescription_id: str
	filename: str
	status: str


class ExtractionResponse(BaseModel):
	prescription_id: str
	ocr: OCRResult
	prescription: Prescription
	human_verification_required: bool


class AuditCall(BaseModel):
	tool: str
	arguments: dict
	result_received: bool


class EvidenceItem(BaseModel):
	text: str | None = None
	source: str | None = None
	document_id: str | None = None
	section: str | None = None
	page: int | None = None
	version: int | str | None = None
	jurisdiction: str | None = None
	publication_date: str | None = None
	source_url: str | None = None
	retrieval_similarity_score: float | None = None


class MedicationAnalysis(BaseModel):
	medication: str | None = None
	condition: str | None = None
	dosage: str | None = None
	evidence_status: str
	evidence: list[EvidenceItem] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
	prescription_id: str
	status: str
	human_review_required: bool
	medications: list[MedicationAnalysis] = Field(default_factory=list)
	drug_interactions: dict = Field(default_factory=dict)
	issues: list[str] = Field(default_factory=list)
	audit: dict[str, list[AuditCall]]

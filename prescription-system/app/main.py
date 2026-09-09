"""Prescription upload and extraction API."""

from __future__ import annotations

import secrets
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from .medical_agent import analyze_prescription
from .models import AnalysisResponse, ExtractionResponse, UploadResponse
from .mcp_client import ClinicalMCPClient, ClinicalMCPError
from .ocr import extract_prescription
from .prescription_parser import parse_prescription

app = FastAPI(title="Prescription Analysis Service")

UPLOAD_DIRECTORY = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}
_prescriptions: dict[str, dict[str, str]] = {}
_extractions: dict[str, ExtractionResponse] = {}
_analyses: dict[str, AnalysisResponse] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload-prescription", response_model=UploadResponse)
async def upload_prescription(file: UploadFile = File(...)) -> UploadResponse:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    expected_type = ALLOWED_TYPES.get(extension)
    if expected_type is None or file.content_type != expected_type:
        raise HTTPException(status_code=400, detail="Unsupported prescription file type")
    data = await file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Prescription file exceeds the 10 MB limit")
    prescription_id = f"RX-{secrets.token_hex(6).upper()}"
    stored_path = UPLOAD_DIRECTORY / f"{prescription_id}{extension}"
    stored_path.write_bytes(data)
    _prescriptions[prescription_id] = {
        "filename": filename,
        "path": str(stored_path),
        "content_type": expected_type,
    }
    return UploadResponse(prescription_id=prescription_id, filename=filename, status="uploaded")


@app.get("/prescription/{prescription_id}")
def get_prescription(prescription_id: str) -> dict[str, str]:
    record = _prescriptions.get(prescription_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return {"prescription_id": prescription_id, "filename": record["filename"], "status": "uploaded"}


@app.post("/prescription/{prescription_id}/extract", response_model=ExtractionResponse)
def extract_uploaded_prescription(prescription_id: str) -> ExtractionResponse:
    record = _prescriptions.get(prescription_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    ocr_result = extract_prescription(Path(record["path"]), record["content_type"])
    prescription = parse_prescription(ocr_result.raw_text)
    human_review = ocr_result.human_verification_required or bool(
        prescription.uncertain_medications or prescription.warnings
    )
    response = ExtractionResponse(
        prescription_id=prescription_id,
        ocr=ocr_result,
        prescription=prescription,
        human_verification_required=human_review,
    )
    _extractions[prescription_id] = response
    return response


@app.post("/prescription/{prescription_id}/mcp-check")
async def mcp_check(prescription_id: str) -> dict:
    extracted = _extractions.get(prescription_id)
    if extracted is None:
        raise HTTPException(status_code=409, detail="Extract the prescription before running the MCP check")

    medications = extracted.prescription.medications
    medication_names = [medication.name for medication in medications]
    client = ClinicalMCPClient()
    try:
        available_tools = await client.connect()
        if len(medication_names) >= 2:
            interaction_result = await client.query_drug_interactions(medication_names)
        else:
            interaction_result = {
                "interaction_found": False,
                "drugs": medication_names,
                "interactions": [],
                "note": "At least two extracted medications are required for an interaction query.",
            }
        guideline_evidence = []
        for medication in medications:
            dosage_parts = [medication.strength, medication.dose, medication.frequency]
            dosage = " ".join(part for part in dosage_parts if part) or None
            guideline_evidence.append(await client.search_prescription_guidance(
                medication=medication.name,
                condition=extracted.prescription.condition,
                dosage=dosage,
            ))
        return {
            "prescription_id": prescription_id,
            "mcp": {
                "connected": True,
                "available_tools": available_tools,
                "drug_interactions": interaction_result,
                "guideline_evidence": guideline_evidence,
            },
        }
    except (ClinicalMCPError, OSError) as error:
        return {
            "prescription_id": prescription_id,
            "mcp": {
                "connected": False,
                "error": str(error),
                "human_review_required": True,
            },
        }
    finally:
        with suppress(Exception):
            await client.close()


@app.post("/prescription/{prescription_id}/analyze", response_model=AnalysisResponse)
async def analyze_uploaded_prescription(prescription_id: str) -> AnalysisResponse:
    extracted = _extractions.get(prescription_id)
    if extracted is None:
        raise HTTPException(status_code=404, detail="Extracted prescription not found")
    result = await analyze_prescription(extracted)
    _analyses[prescription_id] = result
    return result

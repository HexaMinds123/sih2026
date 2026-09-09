# Prescription System

This directory is the application boundary around the existing Clinical Guidelines MCP server.

Phase 5 adds a deterministic Medical and Pharmaceutical Agent that analyzes extracted prescriptions through the existing Clinical Guidelines MCP server over stdio. No LLM is used. Prescription upload, image/PDF text extraction, OCR quality flags, conservative structured parsing, and validation remain available. Frontend behavior remains deferred.

The application must call the existing MCP server over stdio. It must not access the Clinical Guidelines MongoDB directly and must not create another vector database.

Planned modules:

- `app/ocr.py` - image OCR, embedded PDF extraction, scanned PDF fallback, and quality flags
- `app/prescription_parser.py` - conservative structured extraction with uncertainty warnings
- `app/mcp_client.py` - MCP stdio client for the existing Clinical Guidelines MCP server
- `app/medical_agent.py` - deterministic prescription analysis and audit trail
- `app/main.py` - FastAPI API
- `app/models.py` - Pydantic API models

## Run

Install dependencies from this directory:

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API keeps uploaded files private under `uploads/` and limits uploads to 10 MB. Supported formats are JPG, JPEG, PNG, and PDF.

## API workflow

Upload a prescription:

```powershell
curl.exe -X POST http://127.0.0.1:8000/upload-prescription `
	-F "file=@C:\path\to\prescription.jpg"
```

Example response:

```json
{
	"prescription_id": "RX-A1B2C3D4E5F6",
	"filename": "prescription.jpg",
	"status": "uploaded"
}
```

Extract OCR and structured prescription data:

```powershell
curl.exe -X POST http://127.0.0.1:8000/prescription/RX-A1B2C3D4E5F6/extract
```

The response includes raw OCR text, confidence, warnings, the extracted patient and medication fields, uncertain medication lines, and `human_verification_required`. Missing values remain `null`.

## OCR requirements

Image OCR uses Pillow, pytesseract, and the native Tesseract executable. Install Tesseract separately and ensure `tesseract.exe` is on `PATH` for image OCR and scanned PDF OCR. PDFs with embedded text are processed directly with pypdf and do not require Tesseract.

OCR never corrects or invents prescription text. Low confidence, empty output, short output, unreadable characters, and missing OCR engine conditions require human verification.

## Scope boundary

Phase 6 adds a React/Vite dashboard over the existing API. The prescription system does not access MongoDB directly, implement RAG, or provide medication recommendations or diagnoses.

## Frontend dashboard

The frontend lives in `frontend/` and uses the existing API only. It does not add endpoints, persist patient data in browser storage, or call external AI services.

Install and start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Start the backend in another terminal:

```powershell
cd prescription-system
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Vite proxies `/api/*` to `http://127.0.0.1:8000/*` during development. To use another backend URL, set `VITE_API_BASE_URL` before starting Vite.

The dashboard workflow is upload, extract, review structured fields, then analyze. It displays OCR warnings, missing values as `Not available`, evidence provenance, retrieval similarity scores, interaction findings, issues, human-review status, and the MCP audit trail. Retrieval similarity is explicitly not a medical confidence or safety score.

The frontend does not generate a `SAFE` or `APPROVED` status.

## MCP connection check

Set the existing Clinical Guidelines MCP directory through `CLINICAL_MCP_PATH`. If omitted, the application uses the sibling `clinical-mcp` directory in this repository. `CLINICAL_MCP_PYTHON` is optional and defaults to the current Python executable.

```powershell
$env:CLINICAL_MCP_PATH = "C:\path\to\sih2026\clinical-mcp"
$env:CLINICAL_MCP_PYTHON = "C:\path\to\python.exe"
uvicorn app.main:app --reload
```

After uploading and extracting a prescription, call:

```powershell
curl.exe -X POST http://127.0.0.1:8000/prescription/RX-A1B2C3D4E5F6/mcp-check
```

The endpoint starts the existing MCP server as a subprocess, completes the handshake, verifies `query_drug_interactions`, `search_clinical_guidance`, and `search_prescription_guidance`, calls the remote tools, and closes the subprocess. It never imports `clinical-mcp/server.py` or accesses MongoDB directly.

If the MCP server is unavailable, the endpoint returns `connected: false` and `human_review_required: true` rather than crashing the API.

## Deterministic analysis

After extraction, analyze the cached prescription:

```powershell
curl.exe -X POST http://127.0.0.1:8000/prescription/RX-A1B2C3D4E5F6/analyze
```

The agent calls `query_drug_interactions()` once for multi-medication prescriptions and calls `search_prescription_guidance()` once per medication. It returns evidence provenance, retrieval similarity scores under the explicit field name `retrieval_similarity_score`, issues, allowed review statuses, and an MCP audit trail.

Allowed statuses are `INFORMATIONAL`, `REVIEW_REQUIRED`, `CRITICAL_REVIEW_REQUIRED`, and `INSUFFICIENT_INFORMATION`. The agent never returns `SAFE` or `APPROVED`, does not diagnose, and does not recommend changing medication.

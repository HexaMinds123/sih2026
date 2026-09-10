# Prescription System

This directory is the application boundary around the existing Clinical Guidelines MCP server.
This directory houses the application services surrounding the Clinical Guidelines MCP server: prescription intake, OCR & regex parsing, the deterministic Medical and Pharmaceutical Agent, and the React/Vite clinical workspace.

Phase 5 adds a deterministic Medical and Pharmaceutical Agent that analyzes extracted prescriptions through the existing Clinical Guidelines MCP server over stdio. No LLM is used. Prescription upload, image/PDF text extraction, OCR quality flags, conservative structured parsing, and validation remain available. Frontend behavior remains deferred.
---

The application must call the existing MCP server over stdio. It must not access the Clinical Guidelines MongoDB directly and must not create another vector database.
## Completed Architecture (Phases 4–6)

Planned modules:
- **Phase 4 (Prescription Intake & OCR Parser)**: Secure upload store (`uploads/`, 10 MB limit), PyMuPDF embedded PDF reader, Pillow/Tesseract image OCR fallback, conservative regex parsing, and uncertainty flags.
- **Phase 5 (Deterministic Medical & Pharma Agent)**: Rule-based agent communicating with the Clinical Guidelines MCP server over stdio. Queries drug interactions and retrieves sourced clinical evidence with a full MCP audit trail.
- **Phase 6 (Frontend Clinical Workspace)**: Modern React/TypeScript dashboard with drag-and-drop upload, structured review, evidence provenance, interaction highlights, audit drawer, and human-review flags.

- `app/ocr.py` - image OCR, embedded PDF extraction, scanned PDF fallback, and quality flags
- `app/prescription_parser.py` - conservative structured extraction with uncertainty warnings
- `app/mcp_client.py` - MCP stdio client for the existing Clinical Guidelines MCP server
- `app/medical_agent.py` - deterministic prescription analysis and audit trail
- `app/main.py` - FastAPI API
- `app/models.py` - Pydantic API models
---

## Run
## Directory Structure

Install dependencies from this directory:

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```text
prescription-system/
├── README.md                             # This documentation
├── requirements.txt                      # FastAPI, PyMuPDF, Pillow, pytesseract, pydantic
├── sample_prescription.pdf               # Test PDF: Metformin, Aspirin, Warfarin
├── sample_prescription_with_warnings.pdf # Test PDF: Misspelled medication, missing condition
│
├── app/                                  # Backend Python Modules
│   ├── __init__.py
│   ├── main.py                           # FastAPI application endpoints
│   ├── mcp_client.py                     # MCP stdio client managing subprocess connection
│   ├── medical_agent.py                  # Deterministic prescription analysis agent & audit trail
│   ├── models.py                         # Pydantic schemas for requests, responses & evidence
│   ├── ocr.py                            # PDF extraction, image OCR & conservative quality checks
│   └── prescription_parser.py            # Regex-based extraction of patient, condition & meds
│
├── tests/                                # Backend Test Suite (22 test cases)
│   ├── test_api.py                       # FastAPI endpoint tests
│   ├── test_mcp_client.py                # MCP client integration tests
│   ├── test_medical_agent.py             # Agent evaluation & status tests
│   ├── test_ocr.py                       # OCR extraction & quality check tests
│   └── test_parser.py                    # Structured parser regex tests
│
├── uploads/                              # Private prescription file storage (gitignored)
│   └── .gitkeep
│
└── frontend/                             # React / Vite / TypeScript Clinical Dashboard
    ├── package.json                      # Frontend dependencies (React 19, Lucide, Vite, Vitest)
    ├── package-lock.json
    ├── index.html                        # Application HTML shell
    ├── tsconfig.json                     # TypeScript configuration
    ├── vite.config.ts                    # Vite dev proxy to FastAPI backend (:8000)
    ├── vitest.config.ts                  # Vitest test configuration
    │
    └── src/
        ├── App.tsx                       # Clinical workspace UI component
        ├── App.test.tsx                  # Frontend unit tests
        ├── api.ts                        # API service client for FastAPI backend
        ├── types.ts                      # TypeScript schemas
        ├── styles.css                    # Design tokens & clinical layout styles
        ├── main.tsx                      # React root mount
        └── test-setup.ts                 # Vitest test setup
```

The API keeps uploaded files private under `uploads/` and limits uploads to 10 MB. Supported formats are JPG, JPEG, PNG, and PDF.
---

## API workflow
## Quick Start Commands

Upload a prescription:

### 1. Install Backend Dependencies
```powershell
curl.exe -X POST http://127.0.0.1:8000/upload-prescription `
	-F "file=@C:\path\to\prescription.jpg"
python -m pip install -r requirements.txt
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

### 2. Start the FastAPI Backend
```powershell
curl.exe -X POST http://127.0.0.1:8000/prescription/RX-A1B2C3D4E5F6/extract
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- Swagger Docs: `http://127.0.0.1:8000/docs`

The response includes raw OCR text, confidence, warnings, the extracted patient and medication fields, uncertain medication lines, and `human_verification_required`. Missing values remain `null`.

## OCR requirements

Image OCR uses Pillow, pytesseract, and the native Tesseract executable. Install Tesseract separately and ensure `tesseract.exe` is on `PATH` for image OCR and scanned PDF OCR. PDFs with embedded text are processed directly with pypdf and do not require Tesseract.

OCR never corrects or invents prescription text. Low confidence, empty output, short output, unreadable characters, and missing OCR engine conditions require human verification.

## Scope boundary

Phase 6 adds a React/Vite dashboard over the existing API. The prescription system does not access MongoDB directly, implement RAG, or provide medication recommendations or diagnoses.

## Frontend dashboard

The frontend lives in `frontend/` and uses the existing API only. It does not add endpoints, persist patient data in browser storage, or call external AI services.

Install and start the frontend:

### 3. Install & Start the Frontend
In another terminal:
```powershell
cd frontend
npm install
npm run dev
npm run dev -- --host 127.0.0.1 --port 5173
```
- Web App: `http://127.0.0.1:5173`

Start the backend in another terminal:
---

## Running Tests

### Backend Tests (22 tests)
```powershell
cd prescription-system
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
python -m pytest tests
```

Vite proxies `/api/*` to `http://127.0.0.1:8000/*` during development. To use another backend URL, set `VITE_API_BASE_URL` before starting Vite.

The dashboard workflow is upload, extract, review structured fields, then analyze. It displays OCR warnings, missing values as `Not available`, evidence provenance, retrieval similarity scores, interaction findings, issues, human-review status, and the MCP audit trail. Retrieval similarity is explicitly not a medical confidence or safety score.

The frontend does not generate a `SAFE` or `APPROVED` status.

## MCP connection check

Set the existing Clinical Guidelines MCP directory through `CLINICAL_MCP_PATH`. If omitted, the application uses the sibling `clinical-mcp` directory in this repository. `CLINICAL_MCP_PYTHON` is optional and defaults to the current Python executable.

### Frontend Tests (2 tests)
```powershell
$env:CLINICAL_MCP_PATH = "C:\path\to\sih2026\clinical-mcp"
$env:CLINICAL_MCP_PYTHON = "C:\path\to\python.exe"
uvicorn app.main:app --reload
cd frontend
npm test
```

After uploading and extracting a prescription, call:

### Frontend Production Build
```powershell
curl.exe -X POST http://127.0.0.1:8000/prescription/RX-A1B2C3D4E5F6/mcp-check
cd frontend
npm run build
```

The endpoint starts the existing MCP server as a subprocess, completes the handshake, verifies `query_drug_interactions`, `search_clinical_guidance`, and `search_prescription_guidance`, calls the remote tools, and closes the subprocess. It never imports `clinical-mcp/server.py` or accesses MongoDB directly.
---

If the MCP server is unavailable, the endpoint returns `connected: false` and `human_review_required: true` rather than crashing the API.
## API Workflow Endpoints

## Deterministic analysis
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status |
| `POST` | `/upload-prescription` | Uploads a PDF or image file (max 10 MB) to private storage |
| `GET` | `/prescription/{id}` | Retrieves upload status of a prescription |
| `POST` | `/prescription/{id}/extract` | Runs OCR & regex parser to extract structured fields |
| `POST` | `/prescription/{id}/mcp-check` | Tests live stdio MCP connection and tool discovery |
| `POST` | `/prescription/{id}/analyze` | Triggers Medical Agent to query MCP tools and evaluate prescription |

After extraction, analyze the cached prescription:
---

```powershell
curl.exe -X POST http://127.0.0.1:8000/prescription/RX-A1B2C3D4E5F6/analyze
```
## Safety & Governance Disclaimers

The agent calls `query_drug_interactions()` once for multi-medication prescriptions and calls `search_prescription_guidance()` once per medication. It returns evidence provenance, retrieval similarity scores under the explicit field name `retrieval_similarity_score`, issues, allowed review statuses, and an MCP audit trail.

Allowed statuses are `INFORMATIONAL`, `REVIEW_REQUIRED`, `CRITICAL_REVIEW_REQUIRED`, and `INSUFFICIENT_INFORMATION`. The agent never returns `SAFE` or `APPROVED`, does not diagnose, and does not recommend changing medication.
1. **Non-Diagnostic**: The system provides reference-based decision support. It does not generate medical diagnoses or prescribe treatment changes.
2. **No Approval Statuses**: The application intentionally never generates `SAFE` or `APPROVED` tags. All responses fall strictly under four non-approving review statuses: `INFORMATIONAL`, `REVIEW_REQUIRED`, `CRITICAL_REVIEW_REQUIRED`, and `INSUFFICIENT_INFORMATION`.
3. **Retrieval Scores**: Similarity scores represent vector cosine proximity to reference guidelines and must never be interpreted as medical confidence or clinical safety probabilities.

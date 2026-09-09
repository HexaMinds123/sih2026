# Prescription System

This directory houses the application services surrounding the Clinical Guidelines MCP server: prescription intake, OCR & regex parsing, the deterministic Medical and Pharmaceutical Agent, and the React/Vite clinical workspace.

---

## Completed Architecture (Phases 4–6)

- **Phase 4 (Prescription Intake & OCR Parser)**: Secure upload store (`uploads/`, 10 MB limit), PyMuPDF embedded PDF reader, Pillow/Tesseract image OCR fallback, conservative regex parsing, and uncertainty flags.
- **Phase 5 (Deterministic Medical & Pharma Agent)**: Rule-based agent communicating with the Clinical Guidelines MCP server over stdio. Queries drug interactions and retrieves sourced clinical evidence with a full MCP audit trail.
- **Phase 6 (Frontend Clinical Workspace)**: Modern React/TypeScript dashboard with drag-and-drop upload, structured review, evidence provenance, interaction highlights, audit drawer, and human-review flags.

---

## Directory Structure

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

---

## Quick Start Commands

### 1. Install Backend Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 2. Start the FastAPI Backend
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- Swagger Docs: `http://127.0.0.1:8000/docs`

### 3. Install & Start the Frontend
In another terminal:
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
- Web App: `http://127.0.0.1:5173`

---

## Running Tests

### Backend Tests (22 tests)
```powershell
python -m pytest tests
```

### Frontend Tests (2 tests)
```powershell
cd frontend
npm test
```

### Frontend Production Build
```powershell
cd frontend
npm run build
```

---

## API Workflow Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status |
| `POST` | `/upload-prescription` | Uploads a PDF or image file (max 10 MB) to private storage |
| `GET` | `/prescription/{id}` | Retrieves upload status of a prescription |
| `POST` | `/prescription/{id}/extract` | Runs OCR & regex parser to extract structured fields |
| `POST` | `/prescription/{id}/mcp-check` | Tests live stdio MCP connection and tool discovery |
| `POST` | `/prescription/{id}/analyze` | Triggers Medical Agent to query MCP tools and evaluate prescription |

---

## Safety & Governance Disclaimers

1. **Non-Diagnostic**: The system provides reference-based decision support. It does not generate medical diagnoses or prescribe treatment changes.
2. **No Approval Statuses**: The application intentionally never generates `SAFE` or `APPROVED` tags. All responses fall strictly under four non-approving review statuses: `INFORMATIONAL`, `REVIEW_REQUIRED`, `CRITICAL_REVIEW_REQUIRED`, and `INSUFFICIENT_INFORMATION`.
3. **Retrieval Scores**: Similarity scores represent vector cosine proximity to reference guidelines and must never be interpreted as medical confidence or clinical safety probabilities.

# Clinical Decision Support & Prescription Verification System

> **SIH 2026** — An evidence-grounded, privacy-preserving clinical decision support system combining OCR prescription extraction, deterministic medical & pharmaceutical agent analysis, Model Context Protocol (MCP), and MongoDB Atlas RAG vector retrieval.

---

## System Architecture

```text
  ┌────────────────────────────────────────────────────────┐
  │                 Web Browser (Client)                   │
  │   - Upload PDF / JPG / PNG prescriptions               │
  │   - Structured OCR extraction review                   │
  │   - Sourced evidence & DailyMed provenance display     │
  │   - Interaction alerts & expandable MCP audit trail    │
  └───────────────────────────┬────────────────────────────┘
                              │ HTTP :5173 (Vite Dev Proxy)
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │           FastAPI Backend Service (:8000)              │
  │   - POST /upload-prescription (10 MB limit, private)   │
  │   - POST /prescription/{id}/extract (OCR & Parser)     │
  │   - POST /prescription/{id}/analyze (Medical Agent)    │
  │   - POST /prescription/{id}/mcp-check (Health check)   │
  └─────────────┬────────────────────────────┬─────────────┘
                │                            │
                ▼                            ▼
  ┌───────────────────────────┐  ┌───────────────────────────┐
  │   OCR & Parsing Engine    │  │  Medical & Pharma Agent   │
  │ - PyMuPDF (Embedded PDF)  │  │ - Deterministic analysis  │
  │ - PyPDF fallback          │  │ - No LLM hallucinations   │
  │ - Pillow + Tesseract OCR  │  │ - Severity assessment     │
  │ - Strict regex parser     │  │ - Non-diagnostic status   │
  └───────────────────────────┘  └─────────────┬─────────────┘
                                               │ stdio (JSON-RPC)
                                               ▼
  ┌────────────────────────────────────────────────────────┐
  │           Clinical Guidelines MCP Server               │
  │   - query_drug_interactions(meds_list)                 │
  │   - search_prescription_guidance(med, cond, dose)      │
  │   - search_clinical_guidance(anomaly_code)             │
  └───────────────────────────┬────────────────────────────┘
                              │ PyMongo
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │              MongoDB Atlas + RAG Engine                │
  │   - Curated drug interactions collection               │
  │   - Curated clinical anomaly guidelines collection     │
  │   - RAG embeddings (`all-MiniLM-L6-v2`) in chunks      │
  │   - U.S. DailyMed / FDA label provenance & metadata    │
  └────────────────────────────────────────────────────────┘
```

---

## Progress Overview: What Has Been Done (Phases 1–6 Complete)

| Phase | Milestone | Deliverables & Scope | Verification Status |
|---|---|---|:---:|
| **Phase 1** | **Clinical Guidelines MCP Server** | FastMCP server exposing tools for drug-drug interaction querying and clinical anomaly guidance. Curated JSON datasets. | **18/18 Tests Passed ✅** |
| **Phase 2** | **MongoDB Atlas + Vector RAG** | Vector database integration using `sentence-transformers/all-MiniLM-L6-v2`, embedding generation, chunking, and cosine similarity ranking. | **Passed ✅** |
| **Phase 3** | **DailyMed Provenance & Grounding** | Curated prescription guidelines with verified U.S. DailyMed / FDA metadata (document ID, section, version, date, jurisdiction, source URL). | **Passed ✅** |
| **Phase 4** | **Prescription Intake & OCR Parser** | FastAPI service with secure upload store (10 MB limit), PyMuPDF/PyPDF text extraction, Pillow/Tesseract OCR, regex-based structured parser, and conservative uncertainty flags. | **Passed ✅** |
| **Phase 5** | **Deterministic Medical & Pharma Agent** | Rule-based agent that orchestrates MCP tools over stdio. Queries interactions, retrieves evidence, calculates statuses, records full tool audit trail. | **22/22 Tests Passed ✅** |
| **Phase 6** | **Frontend UI & Browser E2E Verification** | React + Vite + TypeScript workspace with upload dropzone, extraction review, clinical evidence cards, interaction alerts, audit drawer, non-approval status badges, and Playwright browser E2E test suite. | **2/2 Tests + 12/12 E2E Passed ✅** |
| **Phase 7** | **Orchestration Core Integration** | Connect the Medical & Pharmaceutical Agent to the central multi-agent orchestrator. | *Upcoming* |

---

## Repository Folder Structure

```text
sih2026/
├── README.md                                 # Main project documentation (this file)
├── hi.txt                                    # Repository welcome note
│
├── clinical-mcp/                             # Clinical Guidelines MCP Server & Knowledge Store
│   ├── .env                                  # MongoDB Atlas connection & storage config (private)
│   ├── README.md                             # MCP server detailed documentation
│   ├── requirements.txt                      # MCP Python dependencies (FastMCP, pymongo, sentence-transformers)
│   ├── knowledge.py                          # Knowledge store abstractions (JSON store & Mongo store)
│   ├── rag.py                                # RAG embedding model, chunking, and similarity search
│   ├── seed_mongo.py                         # MongoDB Atlas database seeder & embedding generator
│   ├── server.py                             # FastMCP stdio server entrypoint exposing clinical tools
│   ├── data/
│   │   ├── drug_interactions.json            # Curated drug-drug interactions dataset
│   │   ├── guidelines.json                   # Curated anomaly observation guidelines
│   │   ├── prescription_guidelines.json      # Sourced DailyMed prescription guideline records
│   │   └── rag_evaluation.json               # Benchmark queries for RAG retrieval evaluation
│   └── tests/
│       ├── test_knowledge.py                 # Unit tests for JSON knowledge store
│       ├── test_rag.py                       # Unit tests for embedding model and chunking
│       └── test_server.py                    # Unit tests for MCP server tool endpoints
│
└── prescription-system/                      # Prescription Intake, Agent & Frontend Dashboard
    ├── README.md                             # Prescription system documentation
    ├── requirements.txt                      # FastAPI, PyMuPDF, Pillow, pytesseract, pydantic dependencies
    ├── sample_prescription.pdf               # Test prescription (Metformin + Aspirin + Warfarin)
    ├── sample_prescription_with_warnings.pdf # Test prescription with intentional anomalies
    │
    ├── app/                                  # Backend Application Modules
    │   ├── __init__.py
    │   ├── main.py                           # FastAPI REST endpoints (/upload-prescription, /extract, /analyze)
    │   ├── mcp_client.py                     # Async MCP stdio client managing subprocess lifecycle
    │   ├── medical_agent.py                  # Deterministic prescription analysis agent & audit trail
    │   ├── models.py                         # Pydantic schemas for prescriptions, evidence & analysis
    │   ├── ocr.py                            # Image OCR, PDF extraction & conservative quality checks
    │   └── prescription_parser.py            # Regex-based extraction of patient, condition, and dosing
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
        ├── vite.config.ts                    # Vite bundler config with /api proxy to FastAPI :8000
        ├── vitest.config.ts                  # Vitest unit testing configuration
        │
        └── src/
            ├── App.tsx                       # Primary clinical workspace UI component
            ├── App.test.tsx                  # Frontend unit tests
            ├── api.ts                        # API service client for FastAPI backend
            ├── types.ts                      # TypeScript data definitions
            ├── styles.css                    # Design tokens & clinical layout styles
            ├── main.tsx                      # React root mount
            └── test-setup.ts                 # Vitest test setup
```

---

## Prerequisites

- **Operating System**: Windows, macOS, or Linux
- **Python**: Python 3.12 or higher
- **Node.js**: Node.js 18.x or 22.x with `npm`
- **MongoDB**: MongoDB Atlas cluster (URI configured in `.env`) or a local MongoDB instance
- **Optional**: [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (only required if performing OCR on scanned image files without embedded text)

---

## Configuration (`clinical-mcp/.env`)

Ensure `clinical-mcp/.env` contains your database parameters:

```ini
CLINICAL_MCP_STORAGE=mongo
MONGO_URI=mongodb+srv://<username>:<password>@projects.ktwm3ms.mongodb.net/?appName=projects
MONGO_DATABASE=clinical_knowledge
MONGO_INTERACTIONS_COLLECTION=drug_interactions
MONGO_GUIDELINES_COLLECTION=guidelines
```

*(To run completely offline without MongoDB, set `CLINICAL_MCP_STORAGE=json`)*.

---

## Step-by-Step Start Commands

### Step 1: Install Dependencies

Open your terminal (PowerShell or Bash):

```powershell
# 1. Install Clinical MCP dependencies
cd clinical-mcp
python -m pip install -r requirements.txt

# 2. Install Prescription Backend dependencies
cd ../prescription-system
python -m pip install -r requirements.txt

# 3. Install Frontend dependencies
cd frontend
npm install
cd ../..
```

---

### Step 2: Seed MongoDB Atlas & Generate Embeddings

This step populates MongoDB with curated guidelines, drug interactions, DailyMed reference records, and vector embeddings using `sentence-transformers`:

```powershell
cd clinical-mcp
python seed_mongo.py
cd ..
```

*Expected output: `Seeded 7 interactions, 8 anomaly guidelines, and 20 prescription records into clinical_knowledge`.*

---

### Step 3: Start the FastAPI Backend Service (:8000)

In Terminal 1:

```powershell
cd prescription-system
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API Base URL: `http://127.0.0.1:8000`
- Health check: `http://127.0.0.1:8000/health`
- Interactive API Docs: `http://127.0.0.1:8000/docs`

---

### Step 4: Start the Vite Frontend Dashboard (:5173)

In Terminal 2:

```powershell
cd prescription-system/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

- Web Dashboard URL: **`http://127.0.0.1:5173`**
- The frontend automatically proxies API calls from `/api/*` to `http://127.0.0.1:8000/*`.

---

## Running the Automated Test Suites

### 1. Clinical MCP Server Tests (18 tests)
```powershell
cd clinical-mcp
python -m pytest tests
```
*Validates JSON stores, anomaly code normalizations, RAG embeddings, chunking, and MCP tools.*

### 2. Prescription Backend & Agent Tests (22 tests)
```powershell
cd prescription-system
python -m pytest tests
```
*Validates file uploads, embedded PDF extraction, scanned PDF OCR fallback, regex parsing, stdio MCP client, and deterministic agent reasoning.*

### 3. Frontend Vitest Tests (2 tests)
```powershell
cd prescription-system/frontend
npm test
```
*Validates React dashboard rendering and file validation constraints.*

### 4. Frontend Production Build
```powershell
cd prescription-system/frontend
npm run build
```
*Executes TypeScript compiler (`tsc -b`) and Vite production bundler.*

---

## Verification & Walkthrough Demonstration

A sample test prescription PDF is included at `prescription-system/sample_prescription.pdf` containing:
- **Patient**: Eleanor Vance (Age 58, Female)
- **Condition**: Type 2 Diabetes
- **Medications**: Metformin 500 mg, Aspirin 75 mg, Warfarin 5 mg

### What You Will See in the Dashboard:
1. **Intake**: Drag and drop `sample_prescription.pdf` into the upload zone.
2. **Extraction**: Patient details and medications appear with 95% OCR confidence.
3. **Clinical Analysis**: Click **Analyze Prescription**.
4. **Clinical Evidence**: Metformin evidence is displayed with `EVIDENCE_FOUND` badge and DailyMed provenance (document ID, section, version, jurisdiction, source URL).
5. **Drug Interactions**: High-severity warning: `aspirin + warfarin` — *"May increase bleeding risk"* (`HIGH`).
6. **Audit Trail**: Expand the audit trail drawer to review all 4 MCP stdio calls (`query_drug_interactions` + 3 $\times$ `search_prescription_guidance`).
7. **Compliance**: No `SAFE` or `APPROVED` wording is generated. The system outputs `CRITICAL_REVIEW_REQUIRED` with `Human review required`.

---

## Clinical Safety & Governance Principles

1. **No Automated Approvals**: The system never generates `SAFE` or `APPROVED` tags. All outputs are strictly reference-based clinical decision support.
2. **Deterministic Agent**: The analysis agent evaluates prescriptions deterministically against verified clinical data and does not rely on generative LLM prompts for safety determinations.
3. **Strict Provenance**: Every piece of retrieved clinical guidance links back to official DailyMed / FDA package inserts with verifiable document IDs and section numbers.
4. **Retrieval Metric Transparency**: Scores are labeled explicitly as **Retrieval Similarity Scores** (cosine similarity) to prevent confusion with clinical probabilities or safety confidence levels.
5. **Data Privacy**: Uploaded prescriptions remain isolated in the private local store (`uploads/`) and are never sent to external AI APIs.


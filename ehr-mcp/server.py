"""Patient EHR & Context MCP Server with Clinical-MCP Integration.

This server exposes patient medical context, semantic RAG search, and integrated clinical
safety checks through the Model Context Protocol (FastMCP).
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer as FastMCP

try:
    import database
    if not hasattr(database, "PatientDatabase"):
        raise AttributeError("Wrong database module loaded")
    PatientDatabase = database.PatientDatabase
except (ImportError, AttributeError):
    import importlib.util
    _db_path = Path(__file__).resolve().parent / "database.py"
    _spec = importlib.util.spec_from_file_location("ehr_mcp_database", _db_path)
    _db_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_db_mod)
    PatientDatabase = _db_mod.PatientDatabase

try:
    import rag
    if not hasattr(rag, "MongoPatientRAGStore"):
        raise AttributeError("Wrong rag module loaded")
    MongoPatientRAGStore = rag.MongoPatientRAGStore
except (ImportError, AttributeError):
    import importlib.util
    _rag_path = Path(__file__).resolve().parent / "rag.py"
    _spec = importlib.util.spec_from_file_location("ehr_mcp_rag", _rag_path)
    _rag_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_rag_mod)
    MongoPatientRAGStore = _rag_mod.MongoPatientRAGStore

# Load environment configuration
load_dotenv(Path(__file__).parent / ".env", override=False)

# Initialize MCP server
mcp = FastMCP("ehr-mcp")

# Initialize database and RAG store
_db = PatientDatabase("patients.db")
_rag_store: MongoPatientRAGStore | None = None

# Authorization token from environment
AGENT_API_TOKEN = os.getenv("AGENT_API_TOKEN", "medical-agent-secret-token")


def _get_rag_store() -> MongoPatientRAGStore:
    global _rag_store
    if _rag_store is None:
        _rag_store = MongoPatientRAGStore()
    return _rag_store


def _authorize(token: str) -> dict[str, Any] | None:
    """Server-side authorization check using constant-time string comparison."""
    if not isinstance(token, str) or not secrets.compare_digest(token.strip(), AGENT_API_TOKEN):
        return {
            "error": True,
            "code": "UNAUTHORIZED",
            "message": "Invalid authorization token",
        }
    return None


def _patient_not_found_error(patient_id: str) -> dict[str, Any]:
    """Generate a standardized patient-not-found error dict."""
    return {
        "error": True,
        "code": "PATIENT_NOT_FOUND",
        "message": f"Patient '{patient_id}' not found",
    }


# =====================================================================
# MCP Resources
# =====================================================================

@mcp.resource("patient://profile")
def default_patient_profile() -> dict[str, Any]:
    """Return baseline demonstration patient profile (patient://profile)."""
    return patient_profile("P001")


@mcp.resource("patient://profile/{patient_id}")
def patient_profile(patient_id: str) -> dict[str, Any]:
    """Return patient demographics, allergies, and chronic conditions.

    Trade-off note: MCP resources in this protocol specification do not support
    per-call request parameters for token authorization ergonomics like tools do.
    Therefore, this resource is intentionally restricted to lower-sensitivity
    baseline data (demographics, allergies, conditions). Prescriptions,
    emergency contacts, and full EHR searches require authenticated tool calls.
    """
    if not patient_id or not patient_id.strip():
        return {
            "error": True,
            "code": "MISSING_PATIENT_ID",
            "message": "Patient ID must be provided in the resource URI",
        }

    clean_id = patient_id.strip()
    profile = _db.get_patient_profile(clean_id)
    if profile is None:
        return _patient_not_found_error(clean_id)

    return {
        "patient_id": profile["patient_id"],
        "name": profile["name"],
        "age": profile["age"],
        "gender": profile["gender"],
        "allergies": profile["allergies"],
        "conditions": profile["conditions"],
    }


# =====================================================================
# MCP Tools
# =====================================================================

@mcp.tool()
def fetch_active_prescriptions(patient_id: str, token: str = "") -> dict[str, Any]:
    """Fetch all active prescriptions for a patient. Requires authorization token."""
    auth_err = _authorize(token)
    if auth_err:
        return auth_err

    clean_id = patient_id.strip() if isinstance(patient_id, str) else ""
    if not clean_id:
        return {"error": True, "code": "MISSING_PARAMETER", "message": "Missing patient_id parameter"}

    prescriptions = _db.get_active_prescriptions(clean_id)
    if prescriptions is None:
        return _patient_not_found_error(clean_id)

    return {
        "patient_id": clean_id,
        "prescriptions": prescriptions,
        "count": len(prescriptions),
    }


@mcp.tool()
def get_allergies(patient_id: str, token: str = "") -> dict[str, Any]:
    """Retrieve all documented allergies for a patient. Requires authorization token."""
    auth_err = _authorize(token)
    if auth_err:
        return auth_err

    clean_id = patient_id.strip() if isinstance(patient_id, str) else ""
    if not clean_id:
        return {"error": True, "code": "MISSING_PARAMETER", "message": "Missing patient_id parameter"}

    allergies = _db.get_allergies(clean_id)
    if allergies is None:
        return _patient_not_found_error(clean_id)

    return {
        "patient_id": clean_id,
        "allergies": allergies,
        "count": len(allergies),
    }


@mcp.tool()
def get_medical_conditions(patient_id: str, token: str = "") -> dict[str, Any]:
    """Retrieve all diagnosed chronic conditions for a patient. Requires authorization token."""
    auth_err = _authorize(token)
    if auth_err:
        return auth_err

    clean_id = patient_id.strip() if isinstance(patient_id, str) else ""
    if not clean_id:
        return {"error": True, "code": "MISSING_PARAMETER", "message": "Missing patient_id parameter"}

    conditions = _db.get_medical_conditions(clean_id)
    if conditions is None:
        return _patient_not_found_error(clean_id)

    return {
        "patient_id": clean_id,
        "conditions": conditions,
        "count": len(conditions),
    }


@mcp.tool()
def get_emergency_contact(patient_id: str, token: str = "") -> dict[str, Any]:
    """Retrieve primary emergency contact for a patient. Requires authorization token."""
    auth_err = _authorize(token)
    if auth_err:
        return auth_err

    clean_id = patient_id.strip() if isinstance(patient_id, str) else ""
    if not clean_id:
        return {"error": True, "code": "MISSING_PARAMETER", "message": "Missing patient_id parameter"}

    if not _db.patient_exists(clean_id):
        return _patient_not_found_error(clean_id)

    contact = _db.get_emergency_contact(clean_id)
    if contact is None:
        return {
            "patient_id": clean_id,
            "emergency_contact": None,
            "message": f"No emergency contact listed for patient '{clean_id}'",
        }

    return {
        "patient_id": clean_id,
        "emergency_contact": contact,
    }


@mcp.tool()
def search_patient_context(query: str, token: str = "", limit: int = 10) -> dict[str, Any]:
    """Semantic RAG search across patient medical histories, allergies, and prescriptions.

    Allows AI agents to find relevant patient records using natural language queries
    (e.g., 'patients diagnosed with diabetes and hypertension taking amlodipine').
    """
    auth_err = _authorize(token)
    if auth_err:
        return auth_err

    if not isinstance(query, str) or not query.strip():
        return {
            "error": True,
            "code": "INVALID_QUERY",
            "message": "Query cannot be empty or whitespace only",
        }

    if limit < 1 or limit > 20:
        return {
            "error": True,
            "code": "INVALID_LIMIT",
            "message": "limit must be between 1 and 20",
        }

    results = _get_rag_store().search_patients(query.strip(), limit=limit)
    return {
        "query": query.strip(),
        "count": len(results),
        "results": results,
    }


@mcp.tool()
def unified_search(query: str, token: str = "", search_scope: str = "both", limit: int = 10) -> dict[str, Any]:
    """Unified semantic RAG search across patient records and clinical guidelines.

    Integrates EHR patient context with Clinical Guidelines decision support.
    search_scope options:
    - 'patients': Query only patient EHR chunks
    - 'clinical': Query only clinical guideline chunks
    - 'both': Query both and merge ordered by relevance
    """
    auth_err = _authorize(token)
    if auth_err:
        return auth_err

    if not isinstance(query, str) or not query.strip():
        return {
            "error": True,
            "code": "INVALID_QUERY",
            "message": "Query cannot be empty or whitespace only",
        }

    clean_scope = search_scope.strip().lower() if isinstance(search_scope, str) else ""
    if clean_scope not in ("patients", "clinical", "both"):
        return {
            "error": True,
            "code": "INVALID_SCOPE",
            "message": "search_scope must be 'patients', 'clinical', or 'both'",
        }

    if limit < 1 or limit > 20:
        return {
            "error": True,
            "code": "INVALID_LIMIT",
            "message": "limit must be between 1 and 20",
        }

    results = _get_rag_store().unified_search(query.strip(), search_scope=clean_scope, limit=limit)
    return {
        "query": query.strip(),
        "search_scope": clean_scope,
        "count": len(results),
        "results": results,
    }


@mcp.tool()
def check_patient_drug_safety(patient_id: str, token: str = "") -> dict[str, Any]:
    """Cross-server safety check: checks all active medications of a patient against the Clinical drug interactions database.

    Directly integrates EHR-MCP with Clinical-MCP to alert clinicians of dangerous drug-drug combinations.
    """
    auth_err = _authorize(token)
    if auth_err:
        return auth_err

    clean_id = patient_id.strip() if isinstance(patient_id, str) else ""
    if not clean_id:
        return {"error": True, "code": "MISSING_PARAMETER", "message": "Missing patient_id parameter"}

    prescriptions = _db.get_active_prescriptions(clean_id)
    if prescriptions is None:
        return _patient_not_found_error(clean_id)

    med_list = [rx.get("drug") for rx in prescriptions if rx.get("drug")]
    if len(med_list) < 2:
        return {
            "patient_id": clean_id,
            "active_medications": med_list,
            "interaction_found": False,
            "interactions": [],
            "message": "Patient has fewer than two active medications; no multi-drug interactions possible.",
        }

    # Cross-reference with clinical interactions collection in MongoDB Atlas (or local JSON fallback)
    interactions: list[dict[str, Any]] = []
    try:
        from itertools import combinations
        import re

        def norm(name: str) -> str:
            return re.sub(r"\s+", " ", name.strip().lower())

        mongo_queried = False
        uri = os.getenv("MONGO_URI")
        if uri:
            try:
                from pymongo import MongoClient

                client = MongoClient(uri, serverSelectionTimeoutMS=4000)
                db = client[os.getenv("MONGO_DATABASE", "clinical_knowledge")]
                col = db["drug_interactions"]

                for m1, m2 in combinations(med_list, 2):
                    key = "+".join(sorted((norm(m1), norm(m2))))
                    record = col.find_one({"_key": key}, {"_id": 0})
                    if record:
                        interactions.append({
                            "drugs": [m1, m2],
                            "severity": record.get("severity", "unknown"),
                            "warning": record.get("warning", ""),
                        })
                mongo_queried = True
            except Exception:
                mongo_queried = False

        # Fallback to local clinical-mcp JSON dataset if MongoDB wasn't available
        if not mongo_queried:
            json_file = Path(__file__).parent.parent / "clinical-mcp" / "data" / "drug_interactions.json"
            if json_file.exists():
                import json

                raw_interactions = json.loads(json_file.read_text(encoding="utf-8"))
                for m1, m2 in combinations(med_list, 2):
                    key = "+".join(sorted((norm(m1), norm(m2))))
                    record = raw_interactions.get(key)
                    if record:
                        interactions.append({
                            "drugs": [m1, m2],
                            "severity": record.get("severity", "unknown"),
                            "warning": record.get("warning", ""),
                        })
    except Exception as e:
        return {
            "patient_id": clean_id,
            "active_medications": med_list,
            "error": True,
            "message": f"Could not check clinical interaction database: {str(e)}",
        }

    return {
        "patient_id": clean_id,
        "active_medications": med_list,
        "interaction_found": bool(interactions),
        "interactions": interactions,
        "note": "Cross-server clinical decision support linking EHR active prescriptions with Clinical guidelines.",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")

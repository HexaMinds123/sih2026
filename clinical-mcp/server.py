"""Clinical Guidelines MCP server."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from mcp.server.fastmcp import FastMCP

from knowledge import KnowledgeStore, create_store_from_environment, normalize_anomaly_code, normalize_medication

mcp = FastMCP("clinical-guidelines")
_store: KnowledgeStore | None = None


def _get_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = create_store_from_environment()
    return _store


def _validate_medications(meds_list: list[str]) -> list[str]:
    if not isinstance(meds_list, list) or len(meds_list) < 2:
        raise ValueError("meds_list must contain at least two medications")
    normalized = [normalize_medication(medication) for medication in meds_list]
    if len(set(normalized)) != len(normalized):
        raise ValueError("meds_list must not contain duplicate medications")
    return normalized


@mcp.tool()
def query_drug_interactions(meds_list: list[str]) -> dict[str, Any]:
    """Return curated interaction warnings for a medication list."""
    normalized_medications = _validate_medications(meds_list)
    interactions = []
    for first_medication, second_medication in combinations(normalized_medications, 2):
        record = _get_store().find_interaction(first_medication, second_medication)
        if record:
            interactions.append({
                "drugs": [first_medication, second_medication],
                "severity": record["severity"],
                "warning": record["warning"],
            })

    return {
        "interaction_found": bool(interactions),
        "drugs": normalized_medications,
        "interactions": interactions,
        "note": "Results are reference decision support and do not constitute a diagnosis.",
    }


@mcp.tool()
def search_clinical_guidance(anomaly_code: str) -> dict[str, Any]:
    """Retrieve relevant clinical reference evidence for an observation code."""
    normalized_code = normalize_anomaly_code(anomaly_code)
    guidance = _get_store().find_guidance(normalized_code)
    evidence = _get_store().search_guidance(
        normalized_code,
        limit=5,
        metadata_filter={"kind": "clinical_guideline"},
    )
    if guidance is None:
        return {
            "found": False,
            "anomaly_code": normalized_code,
            "message": "No curated guidance was found for this observation code.",
            "evidence": evidence,
        }
    return {
        "found": True,
        "anomaly_code": normalized_code,
        "parameter": guidance["parameter"],
        "observation": guidance["observation"],
        "recommended_action": guidance["action"],
        "evidence": evidence,
        "note": "This is observation-based decision support, not an automatic diagnosis.",
    }


@mcp.tool()
def search_prescription_guidance(
    medication: str,
    condition: str | None = None,
    dosage: str | None = None,
) -> dict[str, Any]:
    """Retrieve existing clinical evidence relevant to a prescription medication."""
    normalized_medication = normalize_medication(medication)
    if condition is not None and (not isinstance(condition, str) or not condition.strip()):
        raise ValueError("condition must be a non-empty string when provided")
    if dosage is not None and (not isinstance(dosage, str) or not dosage.strip()):
        raise ValueError("dosage must be a non-empty string when provided")

    query_parts = [medication.strip()]
    if condition:
        query_parts.append(condition.strip())
    if dosage:
        query_parts.append(dosage.strip())
    query = " ".join(query_parts) + " clinical guideline"
    retrieved = _get_store().search_guidance(
        query,
        limit=5,
        metadata_filter={"medication": normalized_medication, "kind": "prescription_guideline"},
    )
    evidence = []
    for result in retrieved:
        metadata = result.get("metadata") or {}
        evidence.append({
            "text": result.get("text"),
            "source": result.get("source"),
            "document_id": metadata.get("document_id"),
            "section": metadata.get("section"),
            "page": metadata.get("page"),
            "version": metadata.get("version"),
            "jurisdiction": metadata.get("jurisdiction"),
            "publication_date": metadata.get("publication_date"),
            "topic": metadata.get("topic"),
            "source_url": metadata.get("source_url"),
            "similarity_score": result.get("score"),
        })

    return {
        "medication": normalized_medication,
        "condition": condition.strip() if condition else None,
        "dosage": dosage.strip() if dosage else None,
        "evidence_found": bool(evidence),
        "evidence": evidence,
        "human_review_required": True,
        "reason": None if evidence else "No sufficiently relevant clinical evidence found.",
        "note": "Evidence is decision support only and requires human or clinician review.",
    }


if __name__ == "__main__":
    _get_store()
    mcp.run(transport="stdio")

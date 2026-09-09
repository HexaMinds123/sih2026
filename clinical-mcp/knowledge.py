"""Knowledge stores for the clinical decision-support MCP server."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv

_PAIR_SEPARATOR = "+"


class KnowledgeStore(Protocol):
    def find_interaction(self, first_medication: str, second_medication: str) -> dict[str, str] | None:
        ...

    def find_guidance(self, anomaly_code: str) -> dict[str, str] | None:
        ...

    def search_guidance(
        self,
        query: str,
        limit: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...


def normalize_medication(name: str) -> str:
    """Normalize a medication name for case-insensitive matching."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Medication names must be non-empty strings")
    return re.sub(r"\s+", " ", name.strip().lower())


def interaction_key(first_medication: str, second_medication: str) -> str:
    medications = sorted((normalize_medication(first_medication), normalize_medication(second_medication)))
    if medications[0] == medications[1]:
        raise ValueError("An interaction query requires two different medications")
    return _PAIR_SEPARATOR.join(medications)


def normalize_anomaly_code(anomaly_code: str) -> str:
    if not isinstance(anomaly_code, str) or not anomaly_code.strip():
        raise ValueError("Anomaly code must be a non-empty string")
    return anomaly_code.strip().upper()


def _validate_interactions(data: Any) -> dict[str, dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("Drug interaction data must be a JSON object")
    validated: dict[str, dict[str, str]] = {}
    for raw_key, record in data.items():
        if not isinstance(raw_key, str) or "+" not in raw_key:
            raise ValueError("Interaction keys must contain two medication names separated by '+'")
        first, second = raw_key.split("+", 1)
        key = interaction_key(first, second)
        if not isinstance(record, dict) or not isinstance(record.get("severity"), str) or not isinstance(record.get("warning"), str):
            raise ValueError(f"Invalid interaction record for {raw_key}")
        validated[key] = {"severity": record["severity"], "warning": record["warning"]}
    return validated


def _validate_guidelines(data: Any) -> dict[str, dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("Guideline data must be a JSON object")
    validated: dict[str, dict[str, str]] = {}
    for raw_code, record in data.items():
        if not isinstance(raw_code, str) or not isinstance(record, dict):
            raise ValueError("Invalid guideline record")
        required_fields = ("parameter", "observation", "action")
        if any(not isinstance(record.get(field), str) or not record[field].strip() for field in required_fields):
            raise ValueError(f"Invalid guideline record for {raw_code}")
        validated[normalize_anomaly_code(raw_code)] = {
            "parameter": record["parameter"],
            "observation": record["observation"],
            "action": record["action"],
        }
    return validated


class JsonKnowledgeStore:
    def __init__(self, data_directory: Path | None = None) -> None:
        directory = data_directory or Path(__file__).parent / "data"
        self._interactions = _validate_interactions(
            json.loads((directory / "drug_interactions.json").read_text(encoding="utf-8"))
        )
        self._guidelines = _validate_guidelines(
            json.loads((directory / "guidelines.json").read_text(encoding="utf-8"))
        )
        prescription_path = directory / "prescription_guidelines.json"
        self._prescription_guidelines = json.loads(prescription_path.read_text(encoding="utf-8")) if prescription_path.exists() else []

    def find_interaction(self, first_medication: str, second_medication: str) -> dict[str, str] | None:
        return self._interactions.get(interaction_key(first_medication, second_medication))

    def find_guidance(self, anomaly_code: str) -> dict[str, str] | None:
        return self._guidelines.get(normalize_anomaly_code(anomaly_code))

    def search_guidance(
        self,
        query: str,
        limit: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip().lower()
        matches: list[dict[str, Any]] = []
        for code, record in self._guidelines.items():
            text = " ".join((code, record["parameter"], record["observation"], record["action"])).lower()
            if normalized_query in text:
                matches.append({"text": text, "score": 1.0, "source": f"guidelines.json:{code}", "metadata": {"anomaly_code": code}})
        if not metadata_filter or metadata_filter.get("kind") != "prescription_guideline":
            return sorted(matches, key=lambda result: result["score"], reverse=True)[:limit]
        for record in self._prescription_guidelines:
            metadata = {
                "document_id": record["document_id"],
                "section": record["section"],
                "page": record["page"],
                "version": record["version"],
                "jurisdiction": record["jurisdiction"],
                "publication_date": record["publication_date"],
                "medication": record["medication"],
                "condition": record["condition"],
                "topic": record["topic"],
                "source_url": record["source_url"],
                "kind": "prescription_guideline",
            }
            if metadata_filter and any(metadata.get(key) != value for key, value in metadata_filter.items()):
                continue
            terms = [term for term in re.findall(r"[a-z0-9]+", normalized_query) if len(term) > 2]
            searchable = f"{record['medication']} {record.get('condition') or ''} {record['topic']} {record['text']}".lower()
            overlap = sum(term in searchable for term in terms)
            if overlap:
                matches.append({
                    "text": record["text"],
                    "score": round(overlap / max(len(set(terms)), 1), 4),
                    "source": record["source"],
                    "metadata": metadata,
                })
        return sorted(matches, key=lambda result: result["score"], reverse=True)[:limit]


class MongoKnowledgeStore:
    """MongoDB-backed store using separate collections for reference knowledge."""

    def __init__(self, uri: str, database_name: str, interaction_collection: str = "drug_interactions", guideline_collection: str = "guidelines") -> None:
        try:
            from pymongo import MongoClient
        except ImportError as error:
            raise RuntimeError("MongoDB storage requires the pymongo package") from error

        self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._database = self._client[database_name]
        self._interactions = self._database[interaction_collection]
        self._guidelines = self._database[guideline_collection]
        self._client.admin.command("ping")
        from rag import MongoRAGStore

        self._rag_store = MongoRAGStore(self._client, self._database.name)

    def find_interaction(self, first_medication: str, second_medication: str) -> dict[str, str] | None:
        record = self._interactions.find_one({"_key": interaction_key(first_medication, second_medication)}, {"_id": 0})
        if record is None:
            return None
        return {"severity": str(record["severity"]), "warning": str(record["warning"])}

    def find_guidance(self, anomaly_code: str) -> dict[str, str] | None:
        record = self._guidelines.find_one({"_code": normalize_anomaly_code(anomaly_code)}, {"_id": 0})
        if record is None:
            return None
        return {
            "parameter": str(record["parameter"]),
            "observation": str(record["observation"]),
            "action": str(record["action"]),
        }

    def search_guidance(
        self,
        query: str,
        limit: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return [result.__dict__ for result in self._rag_store.search(query, limit=limit, metadata_filter=metadata_filter)]


def create_store_from_environment() -> KnowledgeStore:
    load_dotenv(Path(__file__).parent / ".env", override=False)
    backend = os.getenv("CLINICAL_MCP_STORAGE", "json").strip().lower()
    if backend == "json":
        return JsonKnowledgeStore()
    if backend != "mongo":
        raise ValueError("CLINICAL_MCP_STORAGE must be either 'json' or 'mongo'")

    uri = os.getenv("MONGO_URI")
    database_name = os.getenv("MONGO_DATABASE", "clinical_knowledge")
    if not uri:
        raise RuntimeError("MONGO_URI is required when CLINICAL_MCP_STORAGE=mongo")
    return MongoKnowledgeStore(
        uri,
        database_name,
        os.getenv("MONGO_INTERACTIONS_COLLECTION", "drug_interactions"),
        os.getenv("MONGO_GUIDELINES_COLLECTION", "guidelines"),
    )

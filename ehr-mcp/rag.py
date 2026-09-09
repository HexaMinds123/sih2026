"""RAG semantic search module for Patient EHR records & unified clinical search.

Enables natural language semantic search across:
1. Patient medical histories, allergies, chronic conditions, and active prescriptions.
2. Clinical reference guidelines (integrated with clinical-mcp).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float
    source: str
    metadata: dict[str, Any]


class EmbeddingModel:
    """Lazy sentence-transformer wrapper."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv(
            "CLINICAL_MCP_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "RAG embeddings require sentence-transformers. Run pip install -r requirements.txt."
                ) from error
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, text: str) -> list[float]:
        vector = self._load().encode(text, normalize_embeddings=True)
        return [float(value) for value in vector]


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> list[str]:
    """Split text into overlapping word chunks (default 700 words, 100 word overlap)."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Document text must be non-empty")
    words = text.split()
    if len(words) <= chunk_size:
        return [text.strip()]
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


def format_patient_document(patient_id: str, db: Any) -> str:
    """Format a patient record into a standard medical narrative for chunking and embedding."""
    profile = db.get_patient_profile(patient_id)
    if profile is None:
        return ""
    prescriptions = db.get_active_prescriptions(patient_id) or []
    contact = db.get_emergency_contact(patient_id) or {}

    allergies_list = profile.get("allergies", [])
    allergies_str = ", ".join(allergies_list) if allergies_list else "No known allergies"

    conditions_list = profile.get("conditions", [])
    conditions_str = ", ".join(conditions_list) if conditions_list else "No chronic conditions"

    rx_items = [
        f"{rx.get('drug', '')} {rx.get('dosage', '')} ({rx.get('frequency', '')})"
        for rx in prescriptions
    ]
    rx_str = ", ".join(rx_items) if rx_items else "No active prescriptions"

    contact_str = (
        f"{contact.get('name', 'None')} ({contact.get('relationship', '')}, {contact.get('phone', '')})"
        if contact.get("name")
        else "None listed"
    )

    narrative = (
        f"Patient ID: {profile.get('patient_id')}. "
        f"Name: {profile.get('name')}. Age: {profile.get('age')}. Gender: {profile.get('gender')}. "
        f"Diagnosed Conditions: {conditions_str}. "
        f"Documented Allergies: {allergies_str}. "
        f"Active Prescriptions: {rx_str}. "
        f"Emergency Contact: {contact_str}."
    )
    return narrative


class MongoPatientRAGStore:
    """Stores embedded patient records and retrieves them via cosine similarity."""

    def __init__(
        self,
        uri: str | None = None,
        database_name: str = "clinical_knowledge",
        collection_name: str = "patient_chunks",
    ) -> None:
        self.uri = uri or os.getenv("MONGO_URI")
        self.database_name = os.getenv("MONGO_DATABASE", database_name)
        self.patient_collection_name = os.getenv("MONGO_PATIENT_RAG_COLLECTION", collection_name)
        self.clinical_collection_name = os.getenv("MONGO_RAG_COLLECTION", "clinical_chunks")
        self._embedding_model = EmbeddingModel()
        self._in_memory_patients: list[dict[str, Any]] = []
        self._client: Any = None
        self._patient_col: Any = None
        self._clinical_col: Any = None

        if self.uri:
            try:
                from pymongo import MongoClient

                self._client = MongoClient(self.uri, serverSelectionTimeoutMS=4000)
                self._client.admin.command("ping")
                db = self._client[self.database_name]
                self._patient_col = db[self.patient_collection_name]
                self._clinical_col = db[self.clinical_collection_name]
            except Exception:
                self._patient_col = None
                self._clinical_col = None

    def upsert_patient_record(self, patient_id: str, narrative_text: str, metadata: dict[str, Any] | None = None) -> int:
        """Embed and store patient narrative text."""
        chunks = chunk_text(narrative_text)
        base_meta = metadata or {}
        base_meta["patient_id"] = patient_id
        base_meta["source"] = "patient"
        docs = []

        for idx, chunk in enumerate(chunks):
            chunk_id = hashlib.sha256(f"{patient_id}:{idx}:{chunk}".encode("utf-8")).hexdigest()
            doc = {
                "_id": chunk_id,
                "patient_id": patient_id,
                "chunk_index": idx,
                "text": chunk,
                "embedding": self._embedding_model.encode(chunk),
                "metadata": base_meta,
            }
            docs.append(doc)

        if self._patient_col is not None:
            self._patient_col.delete_many({"patient_id": patient_id})
            if docs:
                self._patient_col.insert_many(docs)
        else:
            self._in_memory_patients = [d for d in self._in_memory_patients if d.get("patient_id") != patient_id]
            self._in_memory_patients.extend(docs)

        return len(docs)

    def search_patients(self, query: str, limit: int = 10, minimum_score: float = 0.25) -> list[dict[str, Any]]:
        """Search patient records using semantic similarity."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string")
        query_vector = np.asarray(self._embedding_model.encode(query.strip()), dtype=np.float32)

        records = (
            list(self._patient_col.find({}, {"_id": 0}))
            if self._patient_col is not None
            else self._in_memory_patients
        )

        results = []
        for record in records:
            vector = np.asarray(record.get("embedding", []), dtype=np.float32)
            if vector.size == 0 or vector.shape != query_vector.shape:
                continue
            score = float(np.dot(query_vector, vector))
            if score >= minimum_score:
                meta = dict(record.get("metadata", {}))
                meta.setdefault("source", "patient")
                results.append({
                    "patient_id": record.get("patient_id", "unknown"),
                    "text": str(record.get("text", "")),
                    "score": round(score, 4),
                    "source": "patient",
                    "metadata": meta,
                })

        return sorted(results, key=lambda r: r["score"], reverse=True)[:limit]

    def search_clinical(self, query: str, limit: int = 10, minimum_score: float = 0.25) -> list[dict[str, Any]]:
        """Search clinical guidelines chunks from clinical-mcp."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string")
        if self._clinical_col is None:
            return []

        query_vector = np.asarray(self._embedding_model.encode(query.strip()), dtype=np.float32)
        records = list(self._clinical_col.find({}, {"_id": 0}))
        results = []
        for record in records:
            vector = np.asarray(record.get("embedding", []), dtype=np.float32)
            if vector.size == 0 or vector.shape != query_vector.shape:
                continue
            score = float(np.dot(query_vector, vector))
            if score >= minimum_score:
                meta = dict(record.get("metadata", {}))
                meta.setdefault("source", "clinical")
                results.append({
                    "text": str(record.get("text", "")),
                    "score": round(score, 4),
                    "source": "clinical",
                    "metadata": meta,
                })

        return sorted(results, key=lambda r: r["score"], reverse=True)[:limit]

    def unified_search(
        self, query: str, search_scope: str = "both", limit: int = 10, minimum_score: float = 0.25
    ) -> list[dict[str, Any]]:
        """Perform unified semantic search across patients, clinical guidelines, or both."""
        clean_scope = search_scope.strip().lower()
        if clean_scope not in ("patients", "clinical", "both"):
            raise ValueError("search_scope must be 'patients', 'clinical', or 'both'")

        if clean_scope == "patients":
            return self.search_patients(query, limit=limit, minimum_score=minimum_score)
        elif clean_scope == "clinical":
            return self.search_clinical(query, limit=limit, minimum_score=minimum_score)

        # "both" scope: search both and merge
        patient_matches = self.search_patients(query, limit=limit, minimum_score=minimum_score)
        clinical_matches = self.search_clinical(query, limit=limit, minimum_score=minimum_score)

        combined = patient_matches + clinical_matches
        combined.sort(key=lambda item: item["score"], reverse=True)
        return combined[:limit]


class MongoRAGStore(MongoPatientRAGStore):
    """Adapter for MongoRAGStore interface providing backwards and cross-server compatibility."""

    def __init__(self, client: Any = None, database_name: str = "clinical_knowledge", embedding_model: Any = None) -> None:
        super().__init__(database_name=database_name)
        if embedding_model:
            self._embedding_model = embedding_model

    def search(
        self,
        query: str,
        limit: int = 10,
        minimum_score: float = 0.25,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        raw_results = self.search_patients(query, limit=limit, minimum_score=minimum_score)
        chunks = []
        for r in raw_results:
            meta = r.get("metadata", {})
            if metadata_filter and any(meta.get(k) != v for k, v in metadata_filter.items()):
                continue
            chunks.append(
                RetrievedChunk(
                    text=r["text"],
                    score=r["score"],
                    source=r.get("source", "patient"),
                    metadata=meta,
                )
            )
        return chunks

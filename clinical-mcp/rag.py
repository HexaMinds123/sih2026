"""MongoDB-backed retrieval-augmented generation primitives.

The module retrieves evidence only. It does not generate diagnoses or treatment plans.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float
    source: str
    metadata: dict[str, Any]


class EmbeddingModel:
    """Process-cached sentence-transformer wrapper."""

    _models: ClassVar[dict[str, Any]] = {}

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv(
            "CLINICAL_MCP_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self._model = self._load()

    def _load(self) -> Any:
        cached = self._models.get(self.model_name)
        if cached is not None:
            return cached
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "RAG embeddings require sentence-transformers. Install requirements.txt."
            ) from error
        model = SentenceTransformer(self.model_name)
        self._models[self.model_name] = model
        return model

    def encode(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector]


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Document text must be non-empty")
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    words = text.split()
    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


class MongoRAGStore:
    """Stores embedded clinical reference chunks in MongoDB and retrieves by cosine score."""

    def __init__(self, client: Any, database_name: str, embedding_model: EmbeddingModel | None = None) -> None:
        self._database = client[database_name]
        self._chunks = self._database[os.getenv("MONGO_RAG_COLLECTION", "clinical_chunks")]
        self._embedding_model = embedding_model or EmbeddingModel()

    def upsert_document(self, source: str, text: str, metadata: dict[str, Any] | None = None) -> int:
        chunks = chunk_text(text)
        documents = []
        base_metadata = metadata or {}
        for index, chunk in enumerate(chunks):
            chunk_id = hashlib.sha256(f"{source}:{index}:{chunk}".encode("utf-8")).hexdigest()
            documents.append({
                "_id": chunk_id,
                "source": source,
                "chunk_index": index,
                "text": chunk,
                "embedding": self._embedding_model.encode(chunk),
                "metadata": base_metadata,
            })
        if documents:
            self._chunks.delete_many({"source": source})
            self._chunks.insert_many(documents)
        return len(documents)

    def search(
        self,
        query: str,
        limit: int = 5,
        minimum_score: float = 0.25,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("RAG query must be non-empty")
        if limit < 1 or limit > 20:
            raise ValueError("limit must be between 1 and 20")
        query_vector = np.asarray(self._embedding_model.encode(query), dtype=np.float32)
        results: list[RetrievedChunk] = []
        for record in self._chunks.find({}, {"_id": 0}):
            metadata = dict(record.get("metadata", {}))
            if metadata_filter and any(metadata.get(key) != value for key, value in metadata_filter.items()):
                continue
            vector = np.asarray(record.get("embedding", []), dtype=np.float32)
            if vector.size == 0 or vector.shape != query_vector.shape:
                continue
            score = float(np.dot(query_vector, vector))
            if score >= minimum_score:
                results.append(RetrievedChunk(
                    text=str(record["text"]),
                    score=round(score, 4),
                    source=str(record.get("source", "unknown")),
                    metadata=metadata,
                ))
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

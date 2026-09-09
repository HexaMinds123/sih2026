"""Load the curated JSON reference data into MongoDB collections."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from knowledge import interaction_key, normalize_anomaly_code
from rag import MongoRAGStore


DATA_DIRECTORY = Path(__file__).parent / "data"


def seed() -> None:
    try:
        from pymongo import MongoClient
    except ImportError as error:
        raise RuntimeError("MongoDB seeding requires the pymongo package") from error
    load_dotenv(Path(__file__).parent / ".env", override=False)
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI is required")
    database_name = os.getenv("MONGO_DATABASE", "clinical_knowledge")
    interactions_name = os.getenv("MONGO_INTERACTIONS_COLLECTION", "drug_interactions")
    guidelines_name = os.getenv("MONGO_GUIDELINES_COLLECTION", "guidelines")

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    database = client[database_name]

    interactions = json.loads((DATA_DIRECTORY / "drug_interactions.json").read_text(encoding="utf-8"))
    interaction_documents = []
    for raw_key, record in interactions.items():
        first, second = raw_key.split("+", 1)
        interaction_documents.append({
            "_key": interaction_key(first, second),
            "drugs": sorted([first.strip().lower(), second.strip().lower()]),
            "severity": record["severity"],
            "warning": record["warning"],
        })

    guidelines = json.loads((DATA_DIRECTORY / "guidelines.json").read_text(encoding="utf-8"))
    guideline_documents = [
        {
            "_code": normalize_anomaly_code(code),
            "parameter": record["parameter"],
            "observation": record["observation"],
            "action": record["action"],
        }
        for code, record in guidelines.items()
    ]

    interaction_collection = database[interactions_name]
    guideline_collection = database[guidelines_name]
    interaction_collection.delete_many({})
    guideline_collection.delete_many({})
    if interaction_documents:
        interaction_collection.insert_many(interaction_documents)
    if guideline_documents:
        guideline_collection.insert_many(guideline_documents)
    interaction_collection.create_index("_key", unique=True)
    guideline_collection.create_index("_code", unique=True)
    rag_store = MongoRAGStore(client, database_name)
    for code, record in guidelines.items():
        rag_store.upsert_document(
            source=f"guidelines.json:{normalize_anomaly_code(code)}",
            text=(
                f"Anomaly code: {normalize_anomaly_code(code)}. Parameter: {record['parameter']}. "
                f"Observation: {record['observation']}. Recommended action: {record['action']}."
            ),
            metadata={"anomaly_code": normalize_anomaly_code(code), "kind": "clinical_guideline"},
        )
    print(f"Seeded {len(interaction_documents)} interactions and {len(guideline_documents)} guidelines into {database_name}")


if __name__ == "__main__":
    seed()

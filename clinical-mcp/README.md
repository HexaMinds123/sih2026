# Clinical Guidelines MCP Server

This server provides reference-based clinical decision support. It contains no patient records and does not make automatic diagnoses.

## Setup

```powershell
cd clinical-mcp
python -m pip install -r requirements.txt
```

The default backend is local JSON data. To use MongoDB, set these variables:

```powershell
$env:CLINICAL_MCP_STORAGE = "mongo"
$env:MONGO_URI = "mongodb://localhost:27017"
$env:MONGO_DATABASE = "clinical_knowledge"
```

Optional collection variables are `MONGO_INTERACTIONS_COLLECTION` and `MONGO_GUIDELINES_COLLECTION`.

Seed the curated reference data into MongoDB:

```powershell
python seed_mongo.py
```

The seed command replaces the two configured collections with the JSON reference dataset and creates indexes on `_key` and `_code`.

## Run

For the JSON backend:

```powershell
$env:CLINICAL_MCP_STORAGE = "json"
python server.py
```

For MongoDB:

```powershell
$env:CLINICAL_MCP_STORAGE = "mongo"
python server.py
```

The server uses MCP stdio transport for local MCP clients. Configure the client to run `python server.py` with `clinical-mcp` as its working directory and pass the environment variables above.

## Tools

- `query_drug_interactions(meds_list)` checks every medication pair against the curated interaction collection and returns structured severity and warning fields.
- `search_clinical_guidance(anomaly_code)` returns observation context and a recommended verification or clinical-review action.

Unknown records are reported as unknown. The server does not infer interactions, identify diseases, or assert that a patient has a condition.

## Future RAG work

Semantic retrieval, document chunking, embeddings, ChromaDB, and FAISS are intentionally deferred. They can be added behind the same `KnowledgeStore` interface after the JSON and Mongo contracts are stable.

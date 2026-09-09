# Clinical Guidelines MCP Server

This server provides reference-based clinical decision support. It contains no patient records and does not make automatic diagnoses.

## Setup

```powershell
cd clinical-mcp
python -m pip install -r requirements.txt
npx @modelcontextprotocol/inspector python server.py
```

The project includes a local `.env` file for MongoDB settings. Keep that file private and never commit it. The seed script loads it automatically. A shell environment variable takes precedence over values in `.env`.

For a local MongoDB instance, the required configuration is:

```powershell
$env:CLINICAL_MCP_STORAGE = "mongo"
$env:MONGO_URI = "mongodb://localhost:27017"
$env:MONGO_DATABASE = "clinical_knowledge"
```

Optional collection variables are `MONGO_INTERACTIONS_COLLECTION`, `MONGO_GUIDELINES_COLLECTION`, and `MONGO_RAG_COLLECTION`.

RAG uses `sentence-transformers/all-MiniLM-L6-v2` by default. Set `CLINICAL_MCP_EMBEDDING_MODEL` to use another sentence-transformer model. The first seed downloads the model, which is approximately 90 MB, and later runs use the local cache.

## Seed MongoDB

Seed the curated reference data and generate embeddings:

```powershell
python seed_mongo.py
```

The seed command:

1. Connects to MongoDB and verifies the connection with `ping`.
2. Replaces the configured interaction and guideline collections with the JSON dataset.
3. Creates indexes on `_key` and `_code`.
4. Chunks each guideline and generates normalized embeddings.
5. Replaces the matching anomaly and prescription RAG documents in `clinical_chunks`.

The current dataset seeds 7 drug interactions, 8 anomaly guidelines, and 20 prescription-guideline records covering 9 medications: amlodipine, glipizide, ibuprofen, lisinopril, losartan, metformin, omeprazole, simvastatin, and warfarin.

Prescription records are sourced from verified U.S. DailyMed/FDA label pages and retain document ID, section, label version, update date, jurisdiction, and source URL metadata in the existing `clinical_chunks` collection.

If the command reports `No module named 'sentence_transformers'`, install the project dependencies with the same interpreter used to run the seed:

```powershell
python -m pip install -r requirements.txt
python seed_mongo.py
```

If it reports `MONGO_URI is required`, confirm that `.env` is located directly inside `clinical-mcp`, or set `MONGO_URI` in the current PowerShell session.

## Run

For the offline JSON backend:

```powershell
$env:CLINICAL_MCP_STORAGE = "json"
python server.py
```

For MongoDB:

```powershell
$env:CLINICAL_MCP_STORAGE = "mongo"
python server.py
```

The server uses MCP stdio transport for local MCP clients. `python server.py` is a protocol process, not an interactive command prompt: do not type blank lines or tool arguments into its PowerShell window. Every stdin line must be a valid MCP JSON-RPC message. Seeing `Invalid JSON: EOF while parsing` after pressing Enter means the server received an empty line.

Configure an MCP client to run `python server.py` with `clinical-mcp` as its working directory. The Mongo backend requires the same environment variables used by the seed command. For local interactive inspection, use the MCP inspector rather than typing into the server process:

```powershell
npx @modelcontextprotocol/inspector python server.py
```

For a VS Code MCP configuration, use the Python executable and project directory explicitly:

```json
{
	"servers": {
		"clinical-guidelines": {
			"type": "stdio",
			"command": "C:\\Users\\ambat\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
			"args": ["server.py"],
			"cwd": "C:\\Users\\ambat\\OneDrive\\Documents\\GitHub\\sih2026\\clinical-mcp"
		}
	}
}
```

Keep the Mongo environment variables available to the MCP client, or place them in the project `.env` file.

## Tools

- `query_drug_interactions(meds_list)` checks every medication pair against the curated interaction collection and returns structured severity and warning fields.
- `search_clinical_guidance(anomaly_code)` returns observation context, a recommended verification or clinical-review action, and ranked source evidence retrieved from MongoDB embeddings.

Example inputs:

```json
{"meds_list": ["Warfarin", "Aspirin"]}
```

```json
{"anomaly_code": "LOW_SPO2"}
```

The guidance response includes the anomaly code, parameter, observation, recommended action, evidence text, similarity score, and source metadata.

Unknown records are reported as unknown. The server does not infer interactions, identify diseases, assert that a patient has a condition, or generate a diagnosis from retrieved text.

## RAG architecture

1. Reference JSON is converted into clinical documents by `seed_mongo.py`.
2. Documents are split into overlapping chunks.
3. `sentence-transformers` generates normalized embeddings.
4. MongoDB stores source, chunk text, metadata, and embeddings in `clinical_chunks`.
5. A query is embedded and ranked with cosine similarity.
6. The MCP tool returns the matching evidence and structured observation guidance.

The current retrieval implementation is compatible with local MongoDB and MongoDB Atlas because it performs ranking in Python. MongoDB Atlas `$vectorSearch` can replace the ranking loop later for larger corpora without changing the MCP tool contract.

## Verification

Run the automated checks from this directory:

```powershell
python -m pytest -q
python -m compileall -q server.py knowledge.py rag.py seed_mongo.py
```

The JSON backend can be smoke-tested without connecting to MongoDB:

```powershell
$env:CLINICAL_MCP_STORAGE = "json"
python -c "from server import search_clinical_guidance; print(search_clinical_guidance('LOW_SPO2'))"
```

## Safety and provenance

Only curated reference material belongs in this database. Add source, version, jurisdiction, publication date, and review date to future document metadata before using external clinical documents. Do not put patient identifiers, EHR records, or clinical encounter data in this server.

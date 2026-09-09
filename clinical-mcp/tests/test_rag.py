import numpy as np

from rag import MongoRAGStore, chunk_text


class FakeEmbeddingModel:
    def encode(self, text):
        return [1.0, 0.0] if "oxygen" in text.lower() else [0.0, 1.0]


class FakeCollection:
    def __init__(self):
        self.records = {}

    def delete_many(self, query):
        for key in list(self.records):
            if self.records[key]["source"] == query["source"]:
                del self.records[key]

    def insert_many(self, documents):
        self.records.update({document["_id"]: document for document in documents})

    def find(self, query, projection):
        return list(self.records.values())


class FakeDatabase:
    name = "test"

    def __init__(self):
        self.collection = FakeCollection()

    def __getitem__(self, name):
        return self.collection


class FakeClient:
    def __init__(self):
        self.database = FakeDatabase()

    def __getitem__(self, name):
        return self.database


def test_chunking_preserves_text_and_validates_overlap():
    assert chunk_text("one two three", chunk_size=2, overlap=1) == ["one two", "two three"]


def test_mongo_rag_upserts_and_retrieves_relevant_chunks():
    store = MongoRAGStore(FakeClient(), "test", FakeEmbeddingModel())
    assert store.upsert_document("guideline.txt", "Low oxygen saturation guidance") == 1
    assert store.upsert_document("other.txt", "Heart rate guidance") == 1

    results = store.search("oxygen saturation")

    assert len(results) == 1
    assert results[0].source == "guideline.txt"
    assert np.isclose(results[0].score, 1.0)
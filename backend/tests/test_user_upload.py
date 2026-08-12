"""Upload-index unit tests that avoid loading the embedding model."""

import importlib
import sys
import types


def test_upload_index_uses_private_collection_and_owner_filter(monkeypatch):
    class FakeChunker:
        def chunk(self, documents):
            return [{
                "text": documents[0]["content"],
                "metadata": {"source": documents[0]["path"], "chunk_index": 0},
            }]

    class FakeRetriever:
        instances = []

        def __init__(self, collection_name):
            self.collection_name = collection_name
            self.added_chunks = []
            self.search_args = None
            self.__class__.instances.append(self)

        def add_chunks(self, chunks):
            self.added_chunks = chunks
            return ["chunk-id"]

        def search(self, query, k, where):
            self.search_args = (query, k, where)
            return [
                {"text": "own", "source": "upload/own.py", "owner_id": 7},
                {"text": "other", "source": "upload/other.py", "owner_id": 8},
            ]

    fake_chunker = types.ModuleType("app.rag.chunker")
    fake_chunker.CodeChunker = FakeChunker
    fake_dense = types.ModuleType("app.rag.dense_retriever")
    fake_dense.DenseRetriever = FakeRetriever
    fake_dense.USER_CORPUS = {"source_type": "user_upload"}
    fake_dense.USER_UPLOAD_COLLECTION = "user_uploads"

    monkeypatch.setitem(sys.modules, "app.rag.chunker", fake_chunker)
    monkeypatch.setitem(sys.modules, "app.rag.dense_retriever", fake_dense)
    monkeypatch.delitem(sys.modules, "app.rag.user_upload", raising=False)
    module = importlib.import_module("app.rag.user_upload")

    index = module.UserUploadIndex()
    assert index.retriever.collection_name == "user_uploads"

    assert index.add_file("own.py", "private code", owner_id=7) == 1
    metadata = index.retriever.added_chunks[0]["metadata"]
    assert metadata["source_type"] == "user_upload"
    assert metadata["owner_id"] == 7

    assert index.search("private", owner_id=7) == [
        {"text": "own", "source": "upload/own.py", "owner_id": 7}
    ]
    assert index.retriever.search_args == (
        "private", 5, {"source_type": "user_upload", "owner_id": 7}
    )

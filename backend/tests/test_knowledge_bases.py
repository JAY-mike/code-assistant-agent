"""Knowledge-base selection tests without vector stores or Redis."""

import pytest

from app.rag.knowledge_bases import (
    DEFAULT_KNOWLEDGE_BASE,
    KNOWLEDGE_BASES,
    get_knowledge_base,
)


def test_public_knowledge_bases_use_distinct_collections():
    assert DEFAULT_KNOWLEDGE_BASE == "tinydb"
    assert set(KNOWLEDGE_BASES) == {"tinydb", "project"}
    assert KNOWLEDGE_BASES["tinydb"].collection_name != (
        KNOWLEDGE_BASES["project"].collection_name
    )


def test_unknown_knowledge_base_is_rejected():
    with pytest.raises(ValueError, match="Unknown knowledge base"):
        get_knowledge_base("other")


def test_embedding_model_is_reused_within_one_backend_process(monkeypatch):
    from app.rag import dense_retriever

    created = []

    class FakeEmbeddings:
        def __init__(self, **kwargs):
            created.append(kwargs)

    dense_retriever._embedding_models.clear()
    monkeypatch.setattr(dense_retriever, "HuggingFaceEmbeddings", FakeEmbeddings)

    try:
        first = dense_retriever.get_embeddings()
        second = dense_retriever.get_embeddings()

        assert first is second
        assert len(created) == 1
    finally:
        dense_retriever._embedding_models.clear()

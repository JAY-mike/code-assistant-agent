"""Index rebuild state tests without Chroma, Redis, or embedding models."""

import asyncio

from app.rag import code_indexer


def test_rebuild_skips_missing_source_without_creating_a_retriever(monkeypatch):
    monkeypatch.setattr(code_indexer, "load_code_files", lambda _: [])
    monkeypatch.setattr(
        code_indexer,
        "get_knowledge_base",
        lambda _: type("KB", (), {"id": "project", "repo_path": "missing"})(),
    )

    result = asyncio.run(code_indexer.create_index("project"))

    assert result == {
        "status": "skipped",
        "knowledge_base": "project",
        "reason": "No indexable Python files found; existing index was kept",
    }


def test_rebuild_returns_busy_when_another_rebuild_is_running():
    assert code_indexer._rebuild_lock.acquire(blocking=False)
    try:
        result = asyncio.run(code_indexer.create_index("project"))
    finally:
        code_indexer._rebuild_lock.release()

    assert result == {"status": "busy", "knowledge_base": "project"}


def test_rebuild_returns_structured_failure(monkeypatch):
    monkeypatch.setattr(code_indexer, "load_code_files", lambda _: [{"path": "a.py", "content": "x"}])
    monkeypatch.setattr(
        code_indexer,
        "get_knowledge_base",
        lambda _: type("KB", (), {"id": "project", "repo_path": "repo", "collection_name": "project"})(),
    )

    class FailingChunker:
        def __init__(self, **kwargs):
            raise RuntimeError("invalid chunk configuration")

    monkeypatch.setattr(code_indexer, "CodeChunker", FailingChunker)

    result = asyncio.run(code_indexer.create_index("project"))

    assert result["status"] == "failed"
    assert result["knowledge_base"] == "project"
    assert "invalid chunk configuration" in result["reason"]

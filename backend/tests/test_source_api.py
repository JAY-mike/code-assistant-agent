"""Authenticated source viewing tests without an index or external services."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.rag.knowledge_bases import KnowledgeBase
from app.routers import search_router


def _client_for_repo(monkeypatch, repo_path):
    app = FastAPI()
    app.include_router(search_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    knowledge_base = KnowledgeBase(
        id="project",
        label="Test project",
        collection_name="test_collection",
        repo_path=str(repo_path),
    )
    monkeypatch.setattr(search_router, "get_knowledge_base", lambda _: knowledge_base)
    return TestClient(app)


def test_source_endpoint_returns_an_indexable_python_file(monkeypatch, tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "package" / "module.py").write_text("value = 1\n", encoding="utf-8")

    with _client_for_repo(monkeypatch, tmp_path) as client:
        response = client.get(
            "/api/search/source",
            params={"knowledge_base": "project", "source": "package/module.py"},
        )

    assert response.status_code == 200
    assert response.json() == {"source": "package/module.py", "content": "value = 1\n"}


def test_source_endpoint_rejects_path_traversal(monkeypatch, tmp_path):
    with _client_for_repo(monkeypatch, tmp_path) as client:
        response = client.get(
            "/api/search/source",
            params={"knowledge_base": "project", "source": "../.env"},
        )

    assert response.status_code == 400


def test_source_endpoint_hides_non_indexed_directories(monkeypatch, tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_module.py").write_text("assert True\n", encoding="utf-8")

    with _client_for_repo(monkeypatch, tmp_path) as client:
        response = client.get(
            "/api/search/source",
            params={"knowledge_base": "project", "source": "tests/test_module.py"},
        )

    assert response.status_code == 404

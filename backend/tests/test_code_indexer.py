"""Source-selection tests for public knowledge-base indexing."""

from app.rag.code_indexer import load_code_files


def test_project_source_loader_skips_test_and_virtualenv_directories(tmp_path):
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("assert True\n", encoding="utf-8")
    (tmp_path / "env").mkdir()
    (tmp_path / "env" / "dependency.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "generated.py").write_text("value = 2\n", encoding="utf-8")

    documents = load_code_files(str(tmp_path))

    assert documents == [{"path": "app.py", "content": "def run():\n    return 1\n"}]

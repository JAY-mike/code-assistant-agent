"""Contract tests that freeze the reviewed TinyDB retrieval benchmark."""

import hashlib
import json

from app.rag.test_set import TEST_SET, TEST_SET_VERSION


EXPECTED_CASE_COUNT = 20
EXPECTED_SHA256 = "1aea59fb24e1a5e7ece577f5b880a8a1904541604b60eaf4d99f0a0191b8bd4e"


def test_retrieval_dataset_is_versioned_and_reviewed():
    payload = json.dumps(
        TEST_SET,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert TEST_SET_VERSION == "tinydb-retrieval-v1"
    assert len(TEST_SET) == EXPECTED_CASE_COUNT
    assert hashlib.sha256(payload).hexdigest() == EXPECTED_SHA256


def test_retrieval_dataset_has_unique_queries_and_tinydb_evidence():
    queries = [item["query"] for item in TEST_SET]

    assert len(queries) == len(set(queries))
    assert all(item["expected_sources"] for item in TEST_SET)
    assert all(
        source.startswith("tinydb/")
        for item in TEST_SET
        for source in item["expected_sources"]
    )

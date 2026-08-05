"""评估指标单元测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.evaluation import hit_rate, mrr, ndcg


def _make_result(source: str):
    return {"text": "foo", "source": source, "chunk_index": 0, "score": 0.0}


class TestHitRate:
    def test_hit_when_expected_in_top_k(self):
        results = [_make_result("tinydb/database.py")]
        assert hit_rate(results, ["tinydb/database.py"], k=5) == 1.0

    def test_miss_when_expected_not_found(self):
        results = [_make_result("tinydb/table.py")]
        assert hit_rate(results, ["tinydb/database.py"], k=5) == 0.0

    def test_hit_any_expected(self):
        results = [_make_result("tinydb/storages.py")]
        assert hit_rate(results, ["tinydb/database.py", "tinydb/storages.py"], k=5) == 1.0

    def test_windows_backslash_normalized(self):
        results = [_make_result("tinydb\\database.py")]  # Windows 路径
        assert hit_rate(results, ["tinydb/database.py"], k=5) == 1.0


class TestMRR:
    def test_first_rank(self):
        results = [_make_result("tinydb/database.py")]
        assert mrr(results, ["tinydb/database.py"], k=5) == 1.0

    def test_second_rank(self):
        results = [
            _make_result("tinydb/table.py"),
            _make_result("tinydb/database.py"),
        ]
        assert mrr(results, ["tinydb/database.py"], k=5) == 0.5

    def test_no_match(self):
        results = [_make_result("tinydb/table.py")]
        assert mrr(results, ["tinydb/database.py"], k=5) == 0.0


class TestNDCG:
    def test_perfect_ranking(self):
        results = [
            _make_result("tinydb/database.py"),
            _make_result("tinydb/database.py"),
        ]
        assert abs(ndcg(results, ["tinydb/database.py"], k=5) - 1.0) < 0.001

    def test_relevance_at_second(self):
        results = [
            _make_result("tinydb/table.py"),
            _make_result("tinydb/database.py"),
        ]
        assert abs(ndcg(results, ["tinydb/database.py"], k=5) - 0.5) < 0.001

    def test_duplicate_source_credited_once(self):
        results = [
            _make_result("tinydb/database.py"),
            _make_result("tinydb/database.py"),
            _make_result("tinydb/database.py"),
        ]
        # 同一源文件多个 chunk，只算一次相关性，NDCG 应为 1.0（而非大于 1）
        assert abs(ndcg(results, ["tinydb/database.py"], k=5) - 1.0) < 0.001

"""RRF 融合单元测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.fusion import rrf


def _item(source: str, idx: int):
    return {"text": f"chunk {idx}", "source": source, "chunk_index": idx, "score": 0.0}


class TestRRF:
    def test_single_rank(self):
        results_list = [
            [_item("a.py", 0), _item("b.py", 1)],
        ]
        fused = rrf(results_list, top_n=5)
        assert len(fused) == 2
        assert fused[0]["source"] == "a.py"
        assert fused[1]["source"] == "b.py"

    def test_merge_duplicates(self):
        results_list = [
            [_item("a.py", 0)],
            [_item("a.py", 0)],
        ]
        fused = rrf(results_list, top_n=5)
        assert len(fused) == 1  # 同一个 chunk 只出现一次

    def test_rank_boost_from_both_lists(self):
        results_list = [
            [_item("a.py", 0), _item("b.py", 1)],
            [_item("b.py", 1), _item("a.py", 0)],
        ]
        fused = rrf(results_list, top_n=5)
        assert fused[0]["source"] in ("a.py", "b.py")
        assert len(fused) == 2

    def test_top_n_limit(self):
        results_list = [
            [_item(f"f{i}.py", i) for i in range(10)],
        ]
        fused = rrf(results_list, top_n=3)
        assert len(fused) == 3

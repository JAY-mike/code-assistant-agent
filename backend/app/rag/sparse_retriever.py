"""Sparse 检索器：基于 BM25 的关键词检索"""

import os
import re
import json
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class SparseRetriever:
    """基于 BM25 的稀疏检索器"""

    def __init__(self) -> None:
        self.bm25 = None
        self.chunks : list[dict] = []
        self._tokenized: list[list[str]] = []

    def _tokenize(self , text: str) -> list[str]:
        """分词：小写 + 按非字母数字切分 + 过滤短词"""
        tokens = re.findall(r"[a-zA-Z_]\w*" , text.lower())
        return [t for t in tokens if len(t) > 1]

    def build_index(self , chunks: list[dict]):
        """从 chunks 重建 BM25 倒排索引"""
        self.chunks = chunks
        self._tokenized = [self._tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(self._tokenized)
        print(f"[SparseRetriever] Index built with {len(chunks)} chunks")

    def search(self, query: str, k: int = 5) -> list[dict]:
        """检索 top-k 个最相关的代码块"""
        if not query or not query.strip() or not self.bm25:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        top_n_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:k]

        results = []
        for idx in top_n_indices:
            if scores[idx] > 0:
                results.append({
                    "text": self.chunks[idx]["text"],
                    "source": self.chunks[idx]["metadata"]["source"],
                    "chunk_index": self.chunks[idx]["metadata"]["chunk_index"],
                    "score": float(scores[idx]),
                })
        return results

    def count(self) -> int:
        return len(self.chunks) if self.bm25 else 0

    def redis_key(self) -> str:
        """Redis 缓存 key（基于索引内容哈希）"""
        return f"bm25_index: {len(self.chunks)}"

    @classmethod
    def from_chunks(cls , chunks: list[dict]) -> "SparseRetriever":
        """便捷方法：创建 + 建索引"""
        retriever = cls()
        retriever.build_index(chunks)
        return retriever

if __name__ == "__main__":
    from app.rag.chunker import CodeChunker
    from app.rag.code_indexer import load_code_files

    docs = load_code_files(settings.REPO_PATH)
    print(f"Loaded {len(docs)} files")

    chunker = CodeChunker(strategy=settings.CHUNK_STRATEGY)
    chunks = chunker.chunk(docs)
    print(f"Created {len(chunks)} chunks")

    retriever = SparseRetriever.from_chunks(chunks)
    print(f"BM25 index contains {retriever.count()} documents\n")

    for query in ["insert document", "query data", "search table"]:
        results = retriever.search(query, k=3)
        print(f"=== Query: '{query}' ===")
        for r in results:
            print(f"  [{r['source']}] score={r['score']:.2f}  {r['text'][:60]}...")
        print()    
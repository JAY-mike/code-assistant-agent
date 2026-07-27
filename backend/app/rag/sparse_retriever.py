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
        
        #redis缓存
        self.reids_client = None
        try:
            import redis as redis_lib
            self.redis_client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                protocol=2,
            )
            self.reids_client.ping()
        except Exception as e:
            print(f"[SparseRetriever] Redis not available: {e}")
            self.redis_client = None

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
        self._save_to_redis()
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

    def _save_to_redis(self):
        """将 BM25 索引持久化到 Redis"""
        if not self.redis_client or not self.bm25:
            return 
        try:
            data = {
                "chunks": self.chunks,
                "corpus": self._tokenized,
            }
            self.redis_client.setex(
                self.redis_key() , 3600 * 24,
                json.dumps(data , ensure_ascii= False , default= str) 
            )
        except Exception as e:
            print(f"[SparseRetriever] Failed to cache to Redis: {e}")

    @classmethod
    def from_redis(cls) -> "SparseRetriever":
        """尝试从 Redis 恢复 BM25 索引"""
        retriever = cls()
        if not retriever.redis_client:
            return retriever
        try:
            data = retriever.redis_client.get(retriever.redis_key())
            if data:
                parsed = json.load(data)
                retriever.chunks = parsed["chunks"]
                retriever._tokenized = parsed["corpus"]
                retriever.bm25 = BM25Okapi(retriever._tokenized)
                print(f"[SparseRetriever] Restored from Redis ({len(retriever.chunks)} chunks)")
        except Exception as e:
            print(f"[SparseRetriever] Redis restore failed: {e}")
        return retriever         

        
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
"""Sparse 检索器：基于 BM25 的关键词检索"""

import re
import json

from rank_bm25 import BM25Okapi

from app.config import settings
from app.logger import log


class SparseRetriever:
    """基于 BM25 的稀疏检索器"""

    def __init__(self):
        self.bm25 = None
        self.chunks: list[dict] = []
        self._tokenized: list[list[str]] = []

        self.redis_client = None
        try:
            import redis as redis_lib
            self.redis_client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                protocol=2,
            )
            self.redis_client.ping()
        except Exception as e:
            log.warning("Redis not available: %s", e)
            self.redis_client = None

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z_]\w*", text.lower())
        return [t for t in tokens if len(t) > 1]

    def build_index(self, chunks: list[dict]):
        self.chunks = chunks
        self._tokenized = [self._tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(self._tokenized)
        self._save_to_redis()
        log.info("Index built with %d chunks", len(chunks))

    def search(self, query: str, k: int = 5) -> list[dict]:
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
        return f"bm25_index:{settings.CHUNK_STRATEGY}"

    def _save_to_redis(self):
        if not self.redis_client or not self.bm25:
            return
        try:
            data = {
                "chunks": self.chunks,
                "corpus": self._tokenized,
            }
            self.redis_client.setex(
                self.redis_key(), 3600 * 24,
                json.dumps(data, ensure_ascii=False, default=str),
            )
        except Exception as e:
            log.warning("Failed to cache to Redis: %s", e)

    @classmethod
    def from_redis(cls) -> "SparseRetriever":
        retriever = cls()
        if not retriever.redis_client:
            return retriever
        try:
            data = retriever.redis_client.get(retriever.redis_key())
            if data:
                parsed = json.loads(data)
                retriever.chunks = parsed["chunks"]
                retriever._tokenized = parsed["corpus"]
                retriever.bm25 = BM25Okapi(retriever._tokenized)
                log.info("Restored from Redis (%d chunks)", len(retriever.chunks))
        except Exception as e:
            log.warning("Redis restore failed: %s", e)
        return retriever

    @classmethod
    def from_chunks(cls, chunks: list[dict]) -> "SparseRetriever":
        retriever = cls()
        retriever.build_index(chunks)
        return retriever

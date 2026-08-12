"""Cross-encoder 重排序器：对初检结果精排（带 Redis 缓存）"""

import hashlib
import json

from sentence_transformers import CrossEncoder

from app.clients import get_redis_client
from app.config import settings
from app.logger import log


class Reranker:
    """基于 cross-encoder 的精排重排序"""

    def __init__(self):
        model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        log.info("Loading reranker: %s", model_name)
        try:
            self.model = CrossEncoder(model_name)
            log.info("Reranker loaded")
        except Exception as e:
            log.error("Failed to load reranker: %s", e)
            self.model = None

        self.redis_client = get_redis_client()

    def rerank(self, query: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
        if not self.model or not candidates:
            for c in candidates:
                c["rerank_score"] = 0.0
            return candidates[:top_n]

        # 尝试从缓存读取（使用确定性哈希，跨进程一致）
        cache_key = f"rerank:{hashlib.md5(query.encode()).hexdigest()}:{top_n}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        pairs = [(query, c["text"]) for c in candidates]
        scores = self.model.predict(pairs)

        for i, c in enumerate(candidates):
            c["rerank_score"] = float(scores[i])

        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        result = ranked[:top_n]

        log.info("Reranked %d candidates, top score: %.4f",
                 len(candidates), result[0]["rerank_score"] if result else 0)

        # 写入缓存
        if self.redis_client and result:
            try:
                self.redis_client.setex(
                    cache_key, 3600, json.dumps(result, ensure_ascii=False)
                )
            except Exception:
                pass

        return result

    def hybrid_search_with_rerank(
        self,
        query: str,
        dense_retriever,
        sparse_retriever,
        k_dense: int = 10,
        k_sparse: int = 10,
        k_rrf: int = 60,
        top_n: int = 3,
        dense_where: dict | None = None,
    ) -> list[dict]:
        from app.rag.fusion import hybrid_search

        result = hybrid_search(
            query, dense_retriever, sparse_retriever,
            k_dense=k_dense, k_sparse=k_sparse,
            k_rrf=k_rrf, top_n=top_n * 2,
            dense_where=dense_where,
        )

        return self.rerank(query, result["results"], top_n=top_n)

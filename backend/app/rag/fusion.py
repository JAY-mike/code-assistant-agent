"""结果融合：RRF (Reciprocal Rank Fusion) 合并多路检索结果"""

import asyncio
import time
from typing import Any

from app.logger import log


def rrf(
    results_list: list[list[dict[str, Any]]],
    k: int = 60,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    fusion_scores: dict[tuple[str, int], dict] = {}

    for results in results_list:
        for rank, item in enumerate(results):
            key = (item["source"], item["chunk_index"])
            if key not in fusion_scores:
                fusion_scores[key] = {
                    "text": item["text"],
                    "source": item["source"],
                    "chunk_index": item["chunk_index"],
                    "score": 0.0,
                }
            fusion_scores[key]["score"] += 1.0 / (k + rank + 1)

    sorted_items = sorted(
        fusion_scores.values(),
        key=lambda x: x["score"],
        reverse=True,
    )
    return sorted_items[:top_n]


def hybrid_search(
    query: str,
    dense_retriever,
    sparse_retriever,
    k_dense: int = 10,
    k_sparse: int = 10,
    k_rrf: int = 60,
    top_n: int = 5,
    dense_where: dict | None = None,
) -> dict:
    start = time.time()

    dense_results = dense_retriever.search(query, k=k_dense, where=dense_where)
    sparse_results = sparse_retriever.search(query, k=k_sparse)

    log.info("Dense: %d results, Sparse: %d results", len(dense_results), len(sparse_results))

    fused = rrf([dense_results, sparse_results], k=k_rrf, top_n=top_n)

    total_ms = round((time.time() - start) * 1000, 2)
    log.info("Fused: %d, latency: %.2fms", len(fused), total_ms)

    return {
        "results": fused,
        "dense_top_k": dense_results[:3],
        "sparse_top_k": sparse_results[:3],
        "latency_ms": total_ms,
    }


async def async_hybrid_search(
    query: str,
    dense_retriever,
    sparse_retriever,
    k_dense: int = 10,
    k_sparse: int = 10,
    k_rrf: int = 60,
    top_n: int = 5,
    dense_where: dict | None = None,
) -> list[dict[str, Any]]:
    """异步混合检索：用 to_thread 避免阻塞事件循环"""
    result = await asyncio.to_thread(
        hybrid_search,
        query, dense_retriever, sparse_retriever,
        k_dense=k_dense, k_sparse=k_sparse,
        k_rrf=k_rrf, top_n=top_n,
        dense_where=dense_where,
    )

    try:
        from app.database import async_session_factory
        from app.models.retrieval_log import RetrievalLog
        import datetime
        from datetime import UTC

        async with async_session_factory() as session:
            session.add(RetrievalLog(
                query_text=query,
                dense_top_k=result["dense_top_k"],
                sparse_top_k=result["sparse_top_k"],
                fused_top_n=result["results"],
                strategy="hybrid",
                total_latency_ms=result["latency_ms"],
            ))
            await session.commit()
    except Exception as e:
        log.warning("Failed to log retrieval: %s", e)

    return result["results"]

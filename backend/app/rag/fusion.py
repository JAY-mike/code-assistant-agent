"""结果融合：RRF (Reciprocal Rank Fusion) 合并多路检索结果"""

import json
from typing import Any
import time

def rrf(
        results_list : list[list[dict[str,Any]]],
        k: int = 60,
        top_n: int = 5,
) -> list[dict[str,Any]]:
    """
    RRF 融合：合并多路检索结果，按融合分数排序

    参数:
        results_list: 多路结果列表，每路是一个 [{"text":..., "source":..., "score":...}, ...]
        k: RRF 常数，默认 60
        top_n: 最终返回的前 n 个结果

    公式: RRF(d) = Σ 1 / (k + rank_r(d))
    """
    # 用字典聚合：key = (source, chunk_index) → 融合分数
    fusion_scores : dict[tuple[str , int] , dict] = {}
    for results in results_list:
        for rank , item in enumerate(results):
            key = (item["source"] , item["chunk_index"])
            if key not in fusion_scores:
                fusion_scores[key] = {
                    "text": item["text"],
                    "source": item["source"],
                    "chunk_index": item["chunk_index"],
                    "score": 0.0,
                }
                # RRF 累加：排名从 0 开始，所以要 +1
                fusion_scores[key]["score"] += 1.0/(k + rank +1)

    # 按融合分数降序排列
    sorted_items = sorted(
        fusion_scores.values(),
        key=lambda x: x["score"],
        reverse= True,
    )

    return sorted_items[: top_n]

def hybrid_search(
    query: str,
    dense_retriever,
    sparse_retriever,
    k_dense: int = 10,
    k_sparse: int = 10,
    k_rrf: int = 60,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    混合检索：Dense + Sparse → RRF （带检索日志记录）融合

    参数:
        dense_retriever: DenseRetriever 实例
        sparse_retriever: SparseRetriever 实例
        k_dense: dense 路返回 top-k
        k_sparse: sparse 路返回 top-k
        k_rrf: RRF 常数
        top_n: 最终返回 top-n
    """
    dense_results = dense_retriever.search(query, k=k_dense)
    sparse_results = sparse_retriever.search(query, k=k_sparse)

    print(f"[Hybrid] Dense: {len(dense_results)} results, "
          f"Sparse: {len(sparse_results)} results")

    return rrf([dense_results, sparse_results], k=k_rrf, top_n=top_n)

if __name__ == "__main__":
    from app.rag.chunker import CodeChunker
    from app.rag.code_indexer import load_code_files
    from app.rag.dense_retriever import DenseRetriever
    from app.rag.sparse_retriever import SparseRetriever
    from app.config import settings

    # 准备数据
    docs = load_code_files(settings.REPO_PATH)
    chunker = CodeChunker(strategy=settings.CHUNK_STRATEGY)
    chunks = chunker.chunk(docs)
    print(f"Loaded {len(docs)} files, {len(chunks)} chunks\n")

    # 初始化两路检索
    print("Initializing DenseRetriever...")
    dense = DenseRetriever()

    print("Initializing SparseRetriever...")
    sparse = SparseRetriever.from_chunks(chunks)

    # 对比测试
    queries = ["insert document", "query data", "search table"]

    for q in queries:
        print(f"\n{'='*60}")
        print(f"Query: '{q}'")
        print(f"{'='*60}")

        # Dense only
        d = dense.search(q, k=3)
        print(f"\n[Dense only]")
        for r in d:
            print(f"  [{r['source']}] {r['text'][:60]}...")

        # Sparse only
        s = sparse.search(q, k=3)
        print(f"\n[Sparse only]")
        for r in s:
            print(f"  [{r['source']}] score={r['score']:.2f}  {r['text'][:60]}...")

        # Hybrid (RRF)
        h = hybrid_search(q, dense, sparse, k_dense=5, k_sparse=5, top_n=3)
        print(f"\n[Hybrid RRF]")
        for r in h:
            print(f"  [{r['source']}] fusion_score={r['score']:.4f}  {r['text'][:60]}...")
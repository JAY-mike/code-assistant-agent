"""评估引擎：测试集评估 + 指标计算 + 消融实验"""

import time
import asyncio
import logging

from app.rag.test_set import TEST_SET
from app.rag.dense_retriever import DenseRetriever
from app.rag.sparse_retriever import SparseRetriever
from app.rag.fusion import hybrid_search, rrf
from app.rag.reranker import Reranker
from app.rag.query_rewriter import rewrite
from app.logger import log
from functools import partial


def _normalize(source: str) -> str:
    """统一路径分隔符：Windows 反斜杠 → 正斜杠"""
    return source.replace("\\", "/")


def hit_rate(results: list[dict], expected_sources: list[str], k: int = 5) -> float:
    """Hit Rate@k：前k个结果中是否包含至少一个期望的源文件"""
    top_k = results[:k]
    actual_sources = {_normalize(r["source"]) for r in top_k}
    for expected in expected_sources:
        if any(_normalize(expected) in src for src in actual_sources):
            return 1.0
    return 0.0


def mrr(results: list[dict], expected_sources: list[str], k: int = 5) -> float:
    """MRR@k：第一个相关结果的倒数排名"""
    for rank, r in enumerate(results[:k]):
        src = _normalize(r["source"])
        for expected in expected_sources:
            if _normalize(expected) in src:
                return 1.0 / (rank + 1)
    return 0.0


def ndcg(results: list[dict], expected_sources: list[str], k: int = 5) -> float:
    """NDCG@k：归一化折损累积增益（二值相关性）"""
    dcg = 0.0
    matched = set()
    for i, r in enumerate(results[:k]):
        src = _normalize(r["source"])
        rel = 0.0
        for e in expected_sources:
            e_norm = _normalize(e)
            if e_norm in src and e_norm not in matched:
                rel = 1.0
                matched.add(e_norm)
                break
        dcg += rel / (i + 1)

    idcg = 0.0
    for i in range(min(k, len(expected_sources))):
        idcg += 1.0 / (i + 1)

    return dcg / idcg if idcg > 0 else 0.0


async def evaluate_config(
    dense: bool = True,
    sparse: bool = True,
    hyde: bool = False,
    reranker: bool = False,
    top_k: int = 5,
) -> dict:
    """
    运行一轮评估，返回聚合指标
    参数控制消融实验：关掉某个组件就看指标怎么掉
    """
    dense_retriever = DenseRetriever()
    sparse_retriever = SparseRetriever()
    reranker_instance = Reranker() if reranker else None

    total_hit_rate = 0.0
    total_mrr = 0.0
    total_ndcg = 0.0
    total_latency = 0.0
    n = len(TEST_SET)

    for item in TEST_SET:
        query = item["query"]
        expected = item["expected_sources"]
        start = time.time()

        # 第一步：查询改写（HyDE）
        if hyde:
            query = await rewrite(query, strategy="hyde")

        # 第二步：检索（直接同步调用，不走线程池）
        dense_results = []
        sparse_results = []

        if dense_retriever:
            dense_results = dense_retriever.search(query, top_k * 2)

        if sparse_retriever:
            sparse_results = sparse_retriever.search(query, top_k * 2)

        # 第三步：融合
        if dense_results and sparse_results:
            fused = rrf([dense_results, sparse_results], top_n=top_k * 2)
        elif dense_results:
            fused = dense_results[:top_k * 2]
        elif sparse_results:
            fused = sparse_results[:top_k * 2]
        else:
            fused = []

        # 第四步：重排序
        if reranker_instance and fused:
            fused = reranker_instance.rerank(query, fused, top_n=top_k)
        else:
            fused = fused[:top_k]

        latency = time.time() - start
        total_latency += latency

        # 单条日志：谁 + 搜到什么 + 得分
        log.info(
            "[%s] Q: %s... → hits=%d | HR=%.2f MRR=%.2f NDCG=%.2f | %.0fms",
            "HYDE" if hyde else "DIRECT",
            query[:40],
            len(fused),
            hit_rate(fused, expected, k=top_k),
            mrr(fused, expected, k=top_k),
            ndcg(fused, expected, k=top_k),
            latency * 1000,
        )

        # 计算指标
        total_hit_rate += hit_rate(fused, expected, k=top_k)
        total_mrr += mrr(fused, expected, k=top_k)
        total_ndcg += ndcg(fused, expected, k=top_k)

    return {
        "hit_rate": round(total_hit_rate / n, 4),
        "mrr": round(total_mrr / n, 4),
        "ndcg": round(total_ndcg / n, 4),
        "avg_latency_ms": round(total_latency / n * 1000, 2),
        "test_set_size": n,
        "config": {
            "dense": dense,
            "sparse": sparse,
            "hyde": hyde,
            "reranker": reranker,
        },
    }


async def run_ablation(experiment_name: str = "ablation_v1"):
    """
    跑完全部消融实验组合，写入 evaluation_runs 表
    """
    configs = [
        {"dense": True,  "sparse": False, "hyde": False, "reranker": False},
        {"dense": False, "sparse": True,  "hyde": False, "reranker": False},
        {"dense": True,  "sparse": True,  "hyde": False, "reranker": False},
        {"dense": True,  "sparse": True,  "hyde": True,  "reranker": False},
        {"dense": True,  "sparse": True,  "hyde": True,  "reranker": True},
    ]

    names = [
        "dense_only",
        "sparse_only",
        "hybrid_baseline",
        "hybrid_with_hyde",
        "hybrid_with_hyde_and_reranker",
    ]

    results = []
    for cfg, name in zip(configs, names):
        log.info("Running: %s", name)
        print(f"\n--- [{name}] ---")
        result = await evaluate_config(**cfg)
        results.append((name, result))

    # 打印对比表
    print(f"\n{'='*80}")
    print(f"Experiment: {experiment_name}")
    print(f"{'='*80}")
    print(f"{'Config':<30} {'Hit Rate':<10} {'MRR':<10} {'NDCG':<10} {'Latency(ms)':<12}")
    print(f"{'-'*72}")
    for name, r in results:
        print(f"{name:<30} {r['hit_rate']:<10.4f} {r['mrr']:<10.4f} {r['ndcg']:<10.4f} {r['avg_latency_ms']:<12.2f}")
    print(f"{'='*80}")

    # 写入数据库
    from app.database import async_session_factory
    from app.models.evaluation_run import EvaluationRun

    async with async_session_factory() as session:
        for name, r in results:
            session.add(EvaluationRun(
                run_name=f"{experiment_name}_{name}",
                config=r["config"],
                test_set_size=r["test_set_size"],
                hit_rate=r["hit_rate"],
                mrr=r["mrr"],
                ndcg=r["ndcg"],
                avg_latency_ms=r["avg_latency_ms"],
            ))
        await session.commit()

    log.info("Ablation results saved to database")
    return results

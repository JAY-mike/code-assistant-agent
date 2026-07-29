"""评估入口：构建索引 → 跑消融实验 → 写入数据库"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s %(message)s")

from app.rag.code_indexer import load_code_files, save_version_record
from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever
from app.rag.sparse_retriever import SparseRetriever
from app.rag.evaluation import run_ablation
from app.config import settings
from app.database import engine
from app.rag.test_set import TEST_SET

# async def diagnose_index():
#     """打印索引摘要信息"""
#     from app.rag.dense_retriever import DenseRetriever
#     from app.rag.sparse_retriever import SparseRetriever

#     dense = DenseRetriever()
#     count = dense.count()
#     print(f"Dense index: {count} chunks")

#     if count > 0:
#         # 随便搜一条测试查询，看返回什么
#         sample_q = TEST_SET[0]["query"]
#         results = dense.search(sample_q, 5)
#         print(f"\nSample query: '{sample_q[:50]}...'")
#         print(f"Results: {len(results)}")
#         for r in results:
#             print(f"  source={r['source']}, text={r['text'][:60]}...")

#     sparse = SparseRetriever.from_redis()
#     print(f"\nSparse index: {sparse.count()} chunks (from Redis)")
#     if sparse.count() > 0:
#         results2 = sparse.search(sample_q, 5)
#         print(f"Sparse results: {len(results2)}")
#         for r in results2[:3]:
#             print(f"  source={r['source']}, score={r['score']:.2f}")


async def ensure_indexes():
    """确保稠密和稀疏索引都已构建"""

    # 确保 evaluation_runs 表存在
    try:
        async with engine.begin() as conn:
            from app.database import Base
            from app.models.evaluation_run import EvaluationRun  # 确保模型已导入
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Table creation warning: {e}")

    # 1. 检查 dense 索引
    dense = DenseRetriever()
    count = dense.count()
    if count == 0:
        print("Dense index empty, building...")
        documents = load_code_files(settings.REPO_PATH)
        if not documents:
            print("No code files found! Check REPO_PATH")
            return
        chunker = CodeChunker(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunks = chunker.chunk(documents)
        dense.delete_collection()
        dense = DenseRetriever()
        dense.add_chunks(chunks)
        await save_version_record(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            file_count=len(documents),
            chunk_count=len(chunks),
        )
        print(f"Dense index built: {len(chunks)} chunks")
    else:
        print(f"Dense index already exists: {count} chunks")

    # 2. 检查 sparse 索引（尝试从 Redis 恢复）
    sparse = SparseRetriever.from_redis()
    if sparse.count() == 0:
        print("Sparse index empty (no Redis cache), building from files...")
        documents = load_code_files(settings.REPO_PATH)
        if not documents:
            return
        chunker = CodeChunker(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunks = chunker.chunk(documents)
        sparse = SparseRetriever.from_chunks(chunks)
        print(f"Sparse index built: {sparse.count()} chunks")
    else:
        print(f"Sparse index restored: {sparse.count()} chunks")


async def main():
    print("=" * 60)
    print("Step 1: Ensuring indexes are ready...")
    print("=" * 60)
    await ensure_indexes()

    print("\n" + "=" * 60)
    print("Step 2: Running ablation experiments...")
    print("=" * 60)
    results = await run_ablation(experiment_name="ablation_v1")

    print("\n" + "=" * 60)
    print("Done! Results saved to evaluation_runs table.")
    print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    # async def main():
    #     await diagnose_index()
    #     return  # 先停了，看诊断结果再决定要不要跑消融
    asyncio.run(main())
"""代码索引编排器：读取文件 → chunker 分块 → dense_retriever 存储"""

import os
import glob
from threading import Lock
from time import perf_counter
from pathlib import Path

from app.config import settings
from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever
from app.rag.knowledge_bases import (
    DEFAULT_KNOWLEDGE_BASE,
    KNOWLEDGE_BASES,
    get_knowledge_base,
)
from app.rag.sparse_retriever import SparseRetriever
from app.database import async_session_factory
from app.models.index_version import IndexVersion
from app.logger import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EXCLUDED_DIRECTORY_NAMES = {
    ".git", ".pytest_cache", ".venv", "env", "venv", "__pycache__", "data",
}
_rebuild_lock = Lock()


def load_code_files(repo_path: str) -> list[dict]:
    """读取 repo 下所有 .py 文件，返回 [{path, content}]"""
    documents = []
    full_path = repo_path
    if not os.path.isabs(repo_path):
        full_path = str(PROJECT_ROOT / repo_path)

    log.info("Looking for code in: %s", full_path)

    if not os.path.exists(full_path):
        log.error("Path does not exist: %s", full_path)
        return documents

    pattern = os.path.join(full_path, "**", "*.py")
    try:
        matched_files = glob.glob(pattern, recursive=True)
    except Exception as e:
        log.error("Failed to search files: %s", e)
        return documents

    for file_path in matched_files:
        relative_path = Path(os.path.relpath(file_path, full_path))
        if (
            "tests" in relative_path.parts
            or any(part in EXCLUDED_DIRECTORY_NAMES for part in relative_path.parts)
        ):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except PermissionError:
            log.warning("Permission denied: %s", file_path)
            continue
        except UnicodeDecodeError:
            log.warning("Encoding error, trying latin-1: %s", file_path)
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception:
                continue
        except Exception as e:
            log.warning("Failed to read %s: %s", file_path, e)
            continue

        if content.strip():
            documents.append({
                "path": relative_path.as_posix(),
                "content": content,
            })
    return documents


async def save_version_record(strategy: str, chunk_size: int, chunk_overlap: int,
                              file_count: int, chunk_count: int,
                              build_duration_ms: int | None = None):
    """异步写入索引版本记录"""
    try:
        async with async_session_factory() as session:
            session.add(IndexVersion(
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                file_count=file_count,
                chunk_count=chunk_count,
                build_duration_ms=build_duration_ms,
            ))
            await session.commit()
        log.info("Version record saved")
    except Exception as e:
        log.warning("Failed to save version record: %s", e)


async def create_index(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
    """主流程：加载代码 → chunker 分块 → retriever 存储"""
    if not _rebuild_lock.acquire(blocking=False):
        return {"status": "busy", "knowledge_base": knowledge_base_id}

    started_at = perf_counter()
    try:
        knowledge_base = get_knowledge_base(knowledge_base_id)
        log.info("Loading %s code from %s", knowledge_base.id, knowledge_base.repo_path)
        documents = load_code_files(knowledge_base.repo_path)
        log.info("Loaded %d files", len(documents))
        if not documents:
            return {
                "status": "skipped",
                "knowledge_base": knowledge_base.id,
                "reason": "No indexable Python files found; existing index was kept",
            }

        chunker = CodeChunker(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunks = chunker.chunk(documents)
        if not chunks:
            return {
                "status": "skipped",
                "knowledge_base": knowledge_base.id,
                "reason": "Chunking produced no content; existing index was kept",
            }
        log.info("Created %d chunks", len(chunks))

        for chunk in chunks:
            chunk["metadata"]["source_type"] = "system"
            chunk["metadata"]["knowledge_base"] = knowledge_base.id

        retriever = DenseRetriever(collection_name=knowledge_base.collection_name)
        retriever.replace_chunks(chunks)
        sparse = SparseRetriever.from_chunks(chunks, knowledge_base.collection_name)
        duration_ms = round((perf_counter() - started_at) * 1000)
        await save_version_record(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            file_count=len(documents),
            chunk_count=len(chunks),
            build_duration_ms=duration_ms,
        )
        log.info("Index %s built successfully with %d chunks", knowledge_base.id, len(chunks))
        return {
            "status": "ready",
            "knowledge_base": knowledge_base.id,
            "file_count": len(documents),
            "chunk_count": len(chunks),
            "duration_ms": duration_ms,
            "dense": retriever,
            "sparse": sparse,
        }
    except Exception as exc:
        log.exception("Failed to build index %s", knowledge_base_id)
        return {
            "status": "failed",
            "knowledge_base": knowledge_base_id,
            "reason": str(exc),
        }
    finally:
        _rebuild_lock.release()


async def rebuild_index(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
    """对外暴露的"重建索引"接口，后续 API 路由会调用"""
    return await create_index(knowledge_base_id)


async def rebuild_all_indices():
    """Rebuild every public knowledge base without mixing their indexes."""
    results = {}
    for knowledge_base_id in KNOWLEDGE_BASES:
        results[knowledge_base_id] = await create_index(knowledge_base_id)
    return results


if __name__ == "__main__":
    import asyncio

    async def main():
        try:
            results = await rebuild_all_indices()
            for knowledge_base_id, result in results.items():
                print(f"{knowledge_base_id}: {result['status']}")
                if result.get("reason"):
                    print(f"  {result['reason']}")
        finally:
            from app.database import engine
            await engine.dispose()
            log.info("Database connections closed")

    asyncio.run(main())

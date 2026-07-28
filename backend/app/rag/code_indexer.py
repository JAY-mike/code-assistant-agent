"""代码索引编排器：读取文件 → chunker 分块 → dense_retriever 存储"""

import os
import glob
from pathlib import Path

from app.config import settings
from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever
from app.database import async_session_factory
from app.models.index_version import IndexVersion
from app.logger import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


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
        if "__pycache__" in file_path or "/tests/" in file_path or "\\tests\\" in file_path:
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
                "path": os.path.relpath(file_path, full_path),
                "content": content,
            })
    return documents


async def save_version_record(strategy: str, chunk_size: int, chunk_overlap: int,
                              file_count: int, chunk_count: int):
    """异步写入索引版本记录"""
    try:
        async with async_session_factory() as session:
            session.add(IndexVersion(
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                file_count=file_count,
                chunk_count=chunk_count,
            ))
            await session.commit()
        log.info("Version record saved")
    except Exception as e:
        log.warning("Failed to save version record: %s", e)


async def create_index():
    """主流程：加载代码 → chunker 分块 → retriever 存储"""
    log.info("Loading code from %s", settings.REPO_PATH)
    documents = load_code_files(settings.REPO_PATH)
    log.info("Loaded %d files", len(documents))

    if not documents:
        log.error("No .py files found!")
        return

    try:
        chunker = CodeChunker(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
    except Exception as e:
        log.error("Failed to create chunker: %s", e)
        return

    log.info("Using chunk strategy: %s", settings.CHUNK_STRATEGY)
    try:
        chunks = chunker.chunk(documents)
    except Exception as e:
        log.error("Chunking failed: %s", e)
        return
    log.info("Created %d chunks", len(chunks))

    try:
        retriever = DenseRetriever()
        retriever.delete_collection()
        retriever = DenseRetriever()
        retriever.add_chunks(chunks)

        await save_version_record(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            file_count=len(documents),
            chunk_count=len(chunks),
        )

        log.info("Index built successfully with %d chunks", len(chunks))
    except Exception as e:
        log.error("Failed to build index: %s", e)
        return

    return retriever


async def rebuild_index():
    """对外暴露的"重建索引"接口，后续 API 路由会调用"""
    return await create_index()


if __name__ == "__main__":
    import asyncio

    async def main():
        try:
            await create_index()
        finally:
            from app.database import engine
            await engine.dispose()
            log.info("Database connections closed")

    asyncio.run(main())

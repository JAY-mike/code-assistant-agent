"""代码索引编排器：读取文件 → chunker 分块 → dense_retriever 存储"""

import os
import glob
from pathlib import Path

from app.config import settings
from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def load_code_files(repo_path: str) -> list[dict]:
    """读取 repo 下所有 .py 文件，返回 [{path, content}]"""
    documents = []
    full_path = repo_path
    if not os.path.isabs(repo_path):
        full_path = str(PROJECT_ROOT / repo_path)

    print(f"[Indexer] Looking for code in: {full_path}")

    if not os.path.exists(full_path):
        print(f"[Indexer ERROR] Path does not exist: {full_path}")
        return documents

    pattern = os.path.join(full_path, "**", "*.py")
    try:
        matched_files = glob.glob(pattern, recursive=True)
    except Exception as e:
        print(f"[Indexer ERROR] Failed to search files: {e}")
        return documents

    for file_path in matched_files:
        if "__pycache__" in file_path or "/tests/" in file_path or "\\tests\\" in file_path:
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except PermissionError:
            print(f"[Indexer WARNING] Permission denied: {file_path}")
            continue
        except UnicodeDecodeError:
            print(f"[Indexer WARNING] Encoding error, trying latin-1: {file_path}")
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception:
                continue
        except Exception as e:
            print(f"[Indexer WARNING] Failed to read {file_path}: {e}")
            continue

        if content.strip():
            documents.append({
                "path": os.path.relpath(file_path, full_path),
                "content": content,
            })
    return documents


def create_index():
    """主流程：加载代码 → chunker 分块 → retriever 存储"""
    print(f"[Indexer] Loading code from {settings.REPO_PATH}...")
    documents = load_code_files(settings.REPO_PATH)
    print(f"[Indexer] Loaded {len(documents)} files")

    if not documents:
        print("[Indexer ERROR] No .py files found!")
        return

    # 使用配置的分块策略
    try:
        chunker = CodeChunker(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
    except Exception as e:
        print(f"[Indexer ERROR] Failed to create chunker: {e}")
        return

    print(f"[Indexer] Using chunk strategy: {settings.CHUNK_STRATEGY}")
    try:
        chunks = chunker.chunk(documents)
    except Exception as e:
        print(f"[Indexer ERROR] Chunking failed: {e}")
        return
    print(f"[Indexer] Created {len(chunks)} chunks")

    # 存储到 Chroma
    try:
        retriever = DenseRetriever()
        retriever.delete_collection()
        retriever = DenseRetriever()
        retriever.add_chunks(chunks)
        print(f"[Indexer] Index built successfully with {len(chunks)} chunks")
    except Exception as e:
        print(f"[Indexer ERROR] Failed to build index: {e}")
        return

    return retriever


def rebuild_index():
    """对外暴露的"重建索引"接口，后续 API 路由会调用"""
    return create_index()


if __name__ == "__main__":
    create_index()

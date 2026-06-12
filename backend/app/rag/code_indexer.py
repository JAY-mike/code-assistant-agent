import os
import glob
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import settings

# 获取项目根目录（code_indexer.py 所在位置的 parent → parent → parent）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # 项目根目录


def load_code_files(repo_path: str) -> list[dict]:
    """读取 repo 下所有 .py 文件，返回 [{path, content}]"""
    documents = []

    # 如果 repo_path 是相对路径，拼接成绝对路径
    full_path = repo_path
    if not os.path.isabs(repo_path):
        full_path = str(PROJECT_ROOT / repo_path)

    print(f"[RAG] Looking for code in: {full_path}")

    pattern = os.path.join(full_path, "**", "*.py")
    for file_path in glob.glob(pattern, recursive=True):
        # 跳过 __pycache__ 和 tests/
        if "__pycache__" in file_path or "/tests/" in file_path or "\\tests\\" in file_path:
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            documents.append({
                "path": os.path.relpath(file_path, full_path),
                "content": content,
            })
    return documents


def build_chunks(documents: list[dict]) -> list[dict]:
    """把代码文件切分成块，每块附带元信息"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "def ", "class ", "    ", " "],
    )

    chunks = []
    for doc in documents:
        texts = text_splitter.split_text(doc["content"])
        for i, text in enumerate(texts):
            chunks.append({
                "text": text,
                "metadata": {
                    "source": doc["path"],
                    "chunk_index": i,
                },
            })
    return chunks


def create_index():
    """主流程：加载代码 → 分块 → 向量化 → 存入 Chroma"""
    print(f"[RAG] Loading code from {settings.REPO_PATH}...")
    documents = load_code_files(settings.REPO_PATH)
    print(f"[RAG] Loaded {len(documents)} files")

    if not documents:
        print("[RAG ERROR] No .py files found! Check REPO_PATH config.")
        return None

    chunks = build_chunks(documents)
    print(f"[RAG] Created {len(chunks)} chunks")

    print(f"[RAG] Loading embedding model: {settings.EMBEDDING_MODEL}...")
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": settings.EMBEDDING_DEVICE},
    )

    # persist_directory 也用绝对路径
    chroma_path = settings.CHROMA_PERSIST_DIR
    if not os.path.isabs(chroma_path):
        chroma_path = str(PROJECT_ROOT / chroma_path)

    print(f"[RAG] Creating Chroma index at {chroma_path}...")
    vector_store = Chroma.from_texts(
        texts=[c["text"] for c in chunks],
        embedding=embeddings,
        metadatas=[c["metadata"] for c in chunks],
        persist_directory=chroma_path,
    )
    vector_store.persist()
    print(f"[RAG] Index created with {len(chunks)} chunks")

    return vector_store


if __name__ == "__main__":
    create_index()

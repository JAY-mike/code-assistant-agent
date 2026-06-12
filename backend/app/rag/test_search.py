"""快速测试 RAG 检索效果"""
import os
from pathlib import Path

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

chroma_path = settings.CHROMA_PERSIST_DIR
if not os.path.isabs(chroma_path):
    chroma_path = str(PROJECT_ROOT / chroma_path)

embeddings = HuggingFaceEmbeddings(
    model_name=settings.EMBEDDING_MODEL,
    model_kwargs={"device": settings.EMBEDDING_DEVICE},
)

db = Chroma(persist_directory=chroma_path, embedding_function=embeddings)

# 测试几个不同的查询
queries = [
    "insert document",
    "query data",
    "search table",
]

for q in queries:
    print(f"\n=== Query: '{q}' ===")
    results = db.similarity_search(q, k=2)
    for r in results:
        print(f"  [{r.metadata['source']} chunk {r.metadata['chunk_index']}]")
        text = r.page_content[:100].replace("\n", " ")
        print(f"  {text}...")

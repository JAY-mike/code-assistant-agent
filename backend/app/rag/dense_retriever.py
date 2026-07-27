"""Dense 检索器：封装 Chroma 的检索、添加、删除操作"""

import os
from pathlib import Path
from typing import Any

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class DenseRetriever:
    """基于 Chroma 的稠密向量检索器"""

    def __init__(self):
        # 持久化路径
        chroma_path = settings.CHROMA_PERSIST_DIR
        if not os.path.isabs(chroma_path):
            chroma_path = str(PROJECT_ROOT / chroma_path)
        self.persist_dir = chroma_path

        # 确保持久化目录存在
        os.makedirs(self.persist_dir, exist_ok=True)

        # 初始化 embedding 模型
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": settings.EMBEDDING_DEVICE},
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{settings.EMBEDDING_MODEL}': {e}"
            )
        
        # Redis 缓存
        self.redis_client = None
        try:
            import redis as redis_lib
            self.redis_client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                protocol=2,  # 兼容 Redis 6.x 及以下版本
            )
            self.redis_client.ping()
        except Exception as e:
            print(f"[DenseRetriever] Redis not available, caching disabled: {e}")
            self.redis_client = None

        # 加载或创建 Chroma 库
        try:
            self.db = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Chroma at {self.persist_dir}: {e}")

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """检索与 query 最相似的 k 个代码块（带 Redis 缓存）"""
        if not query or not query.strip():
            return []

        # 尝试从缓存读取
        cache_key = f"dense_search:{query.strip()}:{k}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    import json
                    return json.loads(cached)
            except Exception:
                pass  # 缓存读取失败，回退到正常检索

        # 正常检索
        try:
            docs = self.db.similarity_search(query, k=k)
        except Exception as e:
            print(f"[DenseRetriever] Search failed: {e}")
            return []

        results = [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "score": None,
            }
            for doc in docs
        ]

        # 写入缓存
        if self.redis_client and results:
            try:
                import json
                self.redis_client.setex(
                    cache_key, settings.REDIS_CACHE_TTL, json.dumps(results, ensure_ascii=False)
                )
            except Exception:
                pass

        return results

    def search_with_score(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """检索并返回相似度分数（带 Redis 缓存）"""
        if not query or not query.strip():
            return []

        cache_key = f"dense_search_score:{query.strip()}:{k}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    import json
                    return json.loads(cached)
            except Exception:
                pass

        try:
            docs_with_scores = self.db.similarity_search_with_score(query, k=k)
        except Exception as e:
            print(f"[DenseRetriever] Search with score failed: {e}")
            return []

        results = [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "score": score,
            }
            for doc, score in docs_with_scores
        ]

        if self.redis_client and results:
            try:
                import json
                self.redis_client.setex(
                    cache_key, settings.REDIS_CACHE_TTL, json.dumps(results, ensure_ascii=False)
                )
            except Exception:
                pass

        return results

    def add_chunks(self, chunks: list[dict[str, Any]]) -> list[str]:
        """向 Chroma 添加新的代码块"""
        if not chunks:
            print("[DenseRetriever] No chunks to add")
            return []

        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        try:
            ids = self.db.add_texts(texts=texts, metadatas=metadatas)
            return ids
        except Exception as e:
            print(f"[DenseRetriever] Failed to add chunks: {e}")
            return []

    def count(self) -> int:
        """返回当前索引中的文档数量"""
        try:
            return self.db._collection.count()
        except Exception as e:
            print(f"[DenseRetriever] Failed to get count: {e}")
            return 0

    def delete_collection(self):
        """删除整个集合（重建索引时用）"""
        try:
            self.db.delete_collection()
            print("[DenseRetriever] Collection deleted")
        except Exception as e:
            print(f"[DenseRetriever] Delete failed (may not exist): {e}")


if __name__ == "__main__":
    retriever = DenseRetriever()
    count = retriever.count()
    print(f"Index contains {count} documents")

    if count > 0:
        for query in ["insert document", "query data"]:
            results = retriever.search(query, k=2)
            print(f"\n=== Query: '{query}' ===")
            for r in results:
                print(f"  [{r['source']}] {r['text'][:80]}...")
    else:
        print("Index is empty. Run 'python -m app.rag.code_indexer' to build it.")

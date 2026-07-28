"""Dense 检索器：封装 Chroma 的检索、添加、删除操作"""

import os
import json
from pathlib import Path
from typing import Any

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import settings
from app.logger import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class DenseRetriever:
    """基于 Chroma 的稠密向量检索器"""

    def __init__(self):
        chroma_path = settings.CHROMA_PERSIST_DIR
        if not os.path.isabs(chroma_path):
            chroma_path = str(PROJECT_ROOT / chroma_path)
        self.persist_dir = chroma_path

        os.makedirs(self.persist_dir, exist_ok=True)

        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": settings.EMBEDDING_DEVICE},
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{settings.EMBEDDING_MODEL}': {e}"
            )

        self.redis_client = None
        try:
            import redis as redis_lib
            self.redis_client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                protocol=2,
            )
            self.redis_client.ping()
        except Exception as e:
            log.warning("Redis not available, caching disabled: %s", e)
            self.redis_client = None

        try:
            self.db = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Chroma at {self.persist_dir}: {e}")

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []

        cache_key = f"dense_search:{query.strip()}:{k}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        try:
            docs = self.db.similarity_search(query, k=k)
        except Exception as e:
            log.error("Search failed: %s", e)
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

        if self.redis_client and results:
            try:
                self.redis_client.setex(
                    cache_key, settings.REDIS_CACHE_TTL,
                    json.dumps(results, ensure_ascii=False),
                )
            except Exception:
                pass

        return results

    def search_with_score(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []

        cache_key = f"dense_search_score:{query.strip()}:{k}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        try:
            docs_with_scores = self.db.similarity_search_with_score(query, k=k)
        except Exception as e:
            log.error("Search with score failed: %s", e)
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
                self.redis_client.setex(
                    cache_key, settings.REDIS_CACHE_TTL,
                    json.dumps(results, ensure_ascii=False),
                )
            except Exception:
                pass

        return results

    def add_chunks(self, chunks: list[dict[str, Any]]) -> list[str]:
        if not chunks:
            log.warning("No chunks to add")
            return []

        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        try:
            ids = self.db.add_texts(texts=texts, metadatas=metadatas)
            return ids
        except Exception as e:
            log.error("Failed to add chunks: %s", e)
            return []

    def count(self) -> int:
        try:
            return self.db._collection.count()
        except Exception as e:
            log.error("Failed to get count: %s", e)
            return 0

    def delete_collection(self):
        try:
            self.db.delete_collection()
            log.info("Collection deleted")
        except Exception as e:
            log.warning("Delete failed (may not exist): %s", e)

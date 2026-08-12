"""Dense 检索器：封装 Chroma 的检索、添加、删除操作"""

import os
import json
from threading import Lock
from pathlib import Path
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import chromadb

from app.clients import get_redis_client
from app.config import settings
from app.logger import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# 检索范围常量：系统语料 / 用户上传
SYSTEM_CORPUS = {"source_type": "system"}
USER_CORPUS = {"source_type": "user_upload"}
SYSTEM_COLLECTION = "system_code"
USER_UPLOAD_COLLECTION = "user_uploads"

_embedding_models: dict[tuple[str, str], HuggingFaceEmbeddings] = {}
_embedding_models_lock = Lock()
_chroma_clients: dict[str, chromadb.PersistentClient] = {}
_chroma_clients_lock = Lock()


def get_embeddings() -> HuggingFaceEmbeddings:
    """Load each embedding model once per backend process."""
    key = (settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE)
    with _embedding_models_lock:
        embeddings = _embedding_models.get(key)
        if embeddings is None:
            log.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
            embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": settings.EMBEDDING_DEVICE},
            )
            _embedding_models[key] = embeddings
        return embeddings


def get_chroma_client(persist_dir: str) -> chromadb.PersistentClient:
    """Reuse one Chroma persistent client for each on-disk database."""
    path = str(Path(persist_dir).resolve())
    with _chroma_clients_lock:
        client = _chroma_clients.get(path)
        if client is None:
            client = chromadb.PersistentClient(path=path)
            _chroma_clients[path] = client
        return client


class DenseRetriever:
    """基于 Chroma 的稠密向量检索器"""

    def __init__(self, collection_name: str = SYSTEM_COLLECTION):
        self.collection_name = collection_name
        chroma_path = settings.CHROMA_PERSIST_DIR
        if not os.path.isabs(chroma_path):
            chroma_path = str(PROJECT_ROOT / chroma_path)
        self.persist_dir = chroma_path

        os.makedirs(self.persist_dir, exist_ok=True)

        try:
            self.embeddings = get_embeddings()
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{settings.EMBEDDING_MODEL}': {e}"
            )

        self.redis_client = get_redis_client()

        try:
            self.db = Chroma(
                collection_name=self.collection_name,
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
                client=get_chroma_client(self.persist_dir),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Chroma at {self.persist_dir}: {e}")

    def search(self, query: str, k: int = 5,
               where: dict | None = None) -> list[dict[str, Any]]:
        """稠密检索。where 是 Chroma metadata filter，用于隔离检索范围。

        示例：
          search("query")                          # 搜全部（默认）
          search("query", where={"source_type": "system"})
          search("query", where={"owner_id": 1, "source_type": "user_upload"})
        """
        if not query or not query.strip():
            return []

        where_str = json.dumps(where, sort_keys=True) if where else "all"
        cache_key = f"dense_search:{self.collection_name}:{query.strip()}:{k}:{where_str}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        try:
            if where:
                docs = self.db.similarity_search(query, k=k, filter=where)
            else:
                docs = self.db.similarity_search(query, k=k)
        except Exception as e:
            log.error("Search failed: %s", e)
            return []

        results = [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "owner_id": doc.metadata.get("owner_id"),
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

    def search_with_score(self, query: str, k: int = 5,
                          where: dict | None = None) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []

        where_str = json.dumps(where, sort_keys=True) if where else "all"
        cache_key = f"dense_search_score:{self.collection_name}:{query.strip()}:{k}:{where_str}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        try:
            if where:
                docs_with_scores = self.db.similarity_search_with_score(query, k=k, filter=where)
            else:
                docs_with_scores = self.db.similarity_search_with_score(query, k=k)
        except Exception as e:
            log.error("Search with score failed: %s", e)
            return []

        results = [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "owner_id": doc.metadata.get("owner_id"),
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
            self._clear_cache()
            return ids
        except Exception as e:
            log.error("Failed to add chunks: %s", e)
            return []

    def replace_chunks(self, chunks: list[dict[str, Any]]) -> list[str]:
        """Replace a collection while restoring its prior contents on write failure."""
        if not chunks:
            raise ValueError("Cannot replace a collection with no chunks")

        old_documents = []
        old_metadatas = []
        old_ids = []
        try:
            previous = self.db.get(include=["documents", "metadatas"])
            old_documents = previous.get("documents") or []
            old_metadatas = previous.get("metadatas") or []
            old_ids = previous.get("ids") or []
            self.db.delete_collection()
            self.db = Chroma(
                collection_name=self.collection_name,
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
                client=get_chroma_client(self.persist_dir),
            )
            ids = self.add_chunks(chunks)
            if len(ids) != len(chunks):
                raise RuntimeError("Chroma did not store every new chunk")
            return ids
        except Exception as exc:
            log.error("Collection replacement failed: %s", exc)
            try:
                self.db.delete_collection()
                self.db = Chroma(
                    collection_name=self.collection_name,
                    persist_directory=self.persist_dir,
                    embedding_function=self.embeddings,
                    client=get_chroma_client(self.persist_dir),
                )
                if old_documents:
                    self.db.add_texts(
                        texts=old_documents,
                        metadatas=old_metadatas,
                        ids=old_ids,
                    )
                log.warning("Restored previous collection after failed replacement")
            except Exception:
                log.exception("Failed to restore the previous collection")
            raise RuntimeError("Failed to replace collection") from exc

    def count(self) -> int:
        try:
            return self.db._collection.count()
        except Exception as e:
            log.error("Failed to get count: %s", e)
            return 0

    def delete_collection(self):
        try:
            self.db.delete_collection()
            self._clear_cache()
            log.info("Collection deleted")
        except Exception as e:
            log.warning("Delete failed (may not exist): %s", e)

    def _clear_cache(self):
        """清除当前 collection 的检索缓存，避免重建后命中旧结果。"""
        if not self.redis_client:
            return

        try:
            keys = list(self.redis_client.scan_iter(f"dense_search:{self.collection_name}:*"))
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            log.warning("Failed to clear search cache: %s", e)

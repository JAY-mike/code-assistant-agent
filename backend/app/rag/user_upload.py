"""用户文件上传索引：按 owner_id 隔离 + 检索"""

from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever, USER_CORPUS
from app.logger import log


class UserUploadIndex:
    """管理用户上传文件的索引（按 owner_id 隔离）"""

    def __init__(self):
        # 复用 DenseRetriever（Chroma 持久化）
        self.retriever = DenseRetriever()

    def add_file(self, filename: str, content: str, owner_id: int) -> int:
        """索引一个上传的文件，返回生成的 chunk 数

        给每个 chunk 写入 owner_id + source_type 元数据，用于检索时隔离。
        """
        documents = [{"path": f"upload/{filename}", "content": content}]
        chunker = CodeChunker()
        chunks = chunker.chunk(documents)

        for c in chunks:
            c["metadata"]["source_type"] = "user_upload"
            c["metadata"]["owner_id"] = owner_id

        self.retriever.add_chunks(chunks)
        log.info("Indexed upload %s (owner=%d) -> %d chunks", filename, owner_id, len(chunks))
        return len(chunks)

    def search(self, query: str, owner_id: int, k: int = 5) -> list[dict]:
        """只检索指定用户上传的文档

        通过 Chroma metadata filter 在检索端隔离：
        {"source_type": "user_upload", "owner_id": owner_id}
        """
        if not query or not query.strip():
            return []

        where = {**USER_CORPUS, "owner_id": owner_id}
        results = self.retriever.search(query, k=k, where=where)

        # 兜底过滤：防止 Chroma filter 兼容问题导致越权
        return [r for r in results
                if str(r.get("source", "")).startswith("upload/")
                and r.get("owner_id") == owner_id]


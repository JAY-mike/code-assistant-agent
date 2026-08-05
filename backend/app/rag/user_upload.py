"""用户文件上传索引：独立 collection + 检索合并"""

import os
from pathlib import Path
from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever
from app.logger import log

class UserUploadIndex:
    """管理用户上传文件的索引"""

    COLLECTION_NAME = "user_upload"

    def __init__(self) -> None:
        # 用户上传的 collection 复用 DenseRetriever，但换一个 persist 路径
        self.retriever = DenseRetriever()

    def add_file(self , filename: str , content: str) -> int:
        """索引一个上传的文件，返回生成的 chunk 数"""
        documents = [{"path": f"upload/{filename}", "content": content}]
        chunker = CodeChunker()  # 默认 recursive 策略
        chunks = chunker.chunk(documents)

        # 给 chunk 打上来源标记
        for c in chunks:
            c["metadata"]["source_type"] = "user_upload"

        self.retriever.add_chunks(chunks)
        log.info("Indexed upload %s -> %d chunks", filename, len(chunks))
        return len(chunks)

    def search(self, query: str, k: int = 5) -> list[dict]:
        """只在用户上传的文档中检索"""
        return self.retriever.search(query, k=k)
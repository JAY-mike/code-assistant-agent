from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter , TokenTextSplitter

from app.config import settings

class CodeChunker:
    """代码分块器，根据strategy配置选择不同的分块策略"""

    def __init__(
            self,
            strategy: str = "recursive",
            chunk_size: int = 500,
            chunk_overlap : int = 50,
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self , documents: list[dict[str,Any]]) -> list[dict[str,Any]]:
        """入口：根据 strategy 分发到具体策略"""
        if self.strategy == "recursive":
            return self._recursive_chunk(documents)
        elif self.strategy == "token":
            return self._token_chunk(documents)
        elif self.strategy == "semantic":
            return self._sematic_chunk(documents)
        else:
            raise ValueError(f"Unknown chunk strategy: {self.strategy}")
        
    def _recursive_chunk(self,documents: list[dict]) -> list[dict]:
        """递归分块：优先在代码逻辑边界（空行/函数/类）处切分"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size = self.chunk_size,
            chunk_overlap = self.chunk_overlap,
            separators = ["\n\n", "\n", "def ", "class ", "    ", " "],
        )
        return self._apply_splitter(splitter, documents)
    
    def _token_chunk(self , documents: list[dict]) -> list[dict]:
        """Token 分块：按 token 数切，适合对接 LLM 上下文窗口"""        
        splitter = TokenTextSplitter(
            chunk_size=self.chunk_size // 4,
            chunk_overlap=self.chunk_overlap // 4,
        )
        return self._apply_splitter(splitter , documents)
    
    def _sematic_chunk(self , documents: list [ dict]) -> list[dict]:
        """语义分块：在每个函数/类定义前切分，保持代码单元的完整性"""
        chunks = []
        for doc in documents:
            lines = doc["content"].split("\n")
            current_chunk_lines : list[str] = []
            for line in lines:
                if (line.startswith("def") or line.startswith("class")) and current_chunk_lines:
                    indent = len(line) - len(line.lstrip())
                    if indent ==0:
                        text = "\n".join(current_chunk_lines)
                        if text.strip():
                            chunks.append({
                                "text": text,
                                "metadata": {
                                    "source": doc["path"],
                                    "chunk_index": len(chunks),
                                },
                            })
                        current_chunk_lines = []
                current_chunk_lines.append(line)
            if current_chunk_lines:
                text = "\n".join(current_chunk_lines)
                if text.strip():
                    chunks.append({
                        "text": text,
                        "metadata": {
                            "source": doc["path"],
                            "chunk_index": len(chunks),
                        },
                    })
        return chunks
    
    def _apply_splitter(self , splitter , documents : list[dict]) -> list[dict]:
        """通用：把 splitter 应用到所有文档上"""
        chunks = []
        for doc in documents:
            texts = splitter.split_text(doc["content"])
            for i , text in enumerate(texts):
                chunks.append({
                    "text": text,
                    "metadata": {
                        "source": doc["path"],
                        "chunk_index": i,
                    },
                })
        return chunks
    
    def info(self) -> dict:
        """返回当前分块器的配置信息，用于存入 index_versions 表"""
        return {
            "strategy": self.strategy,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

if __name__ == "__main__":
    from app.rag.code_indexer import load_code_files

    docs = load_code_files(settings.REPO_PATH)
    print(f"Loaded {len(docs)} files")

    for strategy in ["recursive", "semantic", "token"]:
        chunker = CodeChunker(strategy=strategy)
        chunks = chunker.chunk(docs)
        print(f"[{strategy}] → {len(chunks)} chunks")                       
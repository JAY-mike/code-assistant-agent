from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter

from app.config import settings


class CodeChunker:
    """代码分块器，根据 strategy 配置选择不同分块策略"""

    def __init__(
        self,
        strategy: str = "recursive",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.strategy == "recursive":
            return self._recursive_chunk(documents)
        elif self.strategy == "token":
            return self._token_chunk(documents)
        elif self.strategy == "semantic":
            return self._semantic_chunk(documents)
        else:
            raise ValueError(f"Unknown chunk strategy: {self.strategy}")

    def _recursive_chunk(self, documents: list[dict]) -> list[dict]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "def ", "class ", "    ", " "],
        )
        return self._apply_splitter(splitter, documents)

    def _token_chunk(self, documents: list[dict]) -> list[dict]:
        splitter = TokenTextSplitter(
            chunk_size=self.chunk_size // 4,
            chunk_overlap=self.chunk_overlap // 4,
        )
        return self._apply_splitter(splitter, documents)

    def _semantic_chunk(self, documents: list[dict]) -> list[dict]:
        chunks = []
        for doc in documents:
            lines = doc["content"].split("\n")
            current_chunk_lines: list[str] = []
            for line in lines:
                if (line.startswith("def ") or line.startswith("class ")) and current_chunk_lines:
                    indent = len(line) - len(line.lstrip())
                    if indent == 0:
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

    def _apply_splitter(self, splitter, documents: list[dict]) -> list[dict]:
        chunks = []
        for doc in documents:
            texts = splitter.split_text(doc["content"])
            for i, text in enumerate(texts):
                chunks.append({
                    "text": text,
                    "metadata": {
                        "source": doc["path"],
                        "chunk_index": i,
                    },
                })
        return chunks

    def info(self) -> dict:
        return {
            "strategy": self.strategy,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

"""Allow-listed tools bound to one public code knowledge base."""

from pydantic import BaseModel, Field

from app.agent.llm import call_llm
from app.agent.tool_base import Tool
from app.config import settings
from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
from app.rag.fusion import rrf
from app.rag.knowledge_bases import DEFAULT_KNOWLEDGE_BASE, get_knowledge_base
from app.rag.sparse_retriever import SparseRetriever


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class TargetArgs(BaseModel):
    target: str = Field(min_length=1, max_length=120)


class CodeTool(Tool):
    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        self.knowledge_base = get_knowledge_base(knowledge_base_id)
        self.last_citations: list[dict] = []

    def _dense_retriever(self) -> DenseRetriever:
        return DenseRetriever(collection_name=self.knowledge_base.collection_name)

    def _search(self, query: str, top_k: int) -> list[dict]:
        dense = self._dense_retriever()
        sparse = SparseRetriever.from_redis(self.knowledge_base.collection_name)
        dense_results = dense.search(query, k=top_k * 2, where=SYSTEM_CORPUS)
        sparse_results = sparse.search(query, k=top_k * 2)
        if dense_results and sparse_results:
            results = rrf([dense_results, sparse_results], top_n=top_k)
        else:
            results = (dense_results or sparse_results)[:top_k]
        self.last_citations = [
            {
                "source": result["source"],
                "excerpt": result["text"][:300],
            }
            for result in results
        ]
        return results


class SearchCode(CodeTool):
    name = "search"
    args_model = SearchArgs

    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        super().__init__(knowledge_base_id)
        self.description = f"Search the {self.knowledge_base.label} codebase for code snippets."

    def execute(self, **kwargs) -> str:
        results = self._search(kwargs["query"], top_k=5)
        if not results:
            return "No results found."
        return "\n---\n".join(
            f"[{result['source']}]\n{result['text'][:300]}\n"
            for result in results
        )


class ExplainCode(CodeTool):
    name = "explain"
    args_model = TargetArgs

    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        super().__init__(knowledge_base_id)
        self.description = f"Explain a function or class from the {self.knowledge_base.label} codebase."

    def execute(self, **kwargs) -> str:
        target = kwargs["target"]
        results = self._search(target, top_k=3)
        if not results:
            return f"Could not find code related to '{target}'."
        context = "\n\n".join(result["text"][:400] for result in results)
        return call_llm(
            f"Explain the role of '{target}' in this code:\n\n{context}",
            system_prompt="You are a Python code tutor. Answer concisely in Chinese.",
            max_retries=0,
            timeout_seconds=settings.AGENT_TOOL_LLM_TIMEOUT_SECONDS,
        )


class GenerateTest(CodeTool):
    name = "testgen"
    args_model = TargetArgs

    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        super().__init__(knowledge_base_id)
        self.description = f"Generate pytest tests for a function or class from the {self.knowledge_base.label} codebase."

    def execute(self, **kwargs) -> str:
        target = kwargs["target"]
        results = self._search(target, top_k=3)
        if not results:
            return f"Could not find code related to '{target}'."
        context = "\n\n".join(result["text"][:500] for result in results)
        return call_llm(
            f"Write pytest tests for '{target}' in the code below:\n\n{context}\n\nOutput code only.",
            system_prompt="You are a Python test engineer. Output runnable pytest code only.",
            max_retries=0,
            timeout_seconds=settings.AGENT_TOOL_LLM_TIMEOUT_SECONDS,
        )


def build_tools(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE) -> list[Tool]:
    return [
        SearchCode(knowledge_base_id),
        ExplainCode(knowledge_base_id),
        GenerateTest(knowledge_base_id),
    ]


AVAILABLE_TOOLS = build_tools()

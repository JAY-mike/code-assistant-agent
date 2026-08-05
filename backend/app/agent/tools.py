"""Agent 工具：search / explain / testgen"""

import json
from app.agent.tool_base import Tool
from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
from app.rag.sparse_retriever import SparseRetriever
from app.rag.fusion import rrf
from app.rag.reranker import Reranker
from app.agent.llm import call_llm

class SearchCode(Tool):
    name = "search"
    description = "在 TinyDB 代码库中搜索与查询最相关的代码片段。支持混合检索（向量+关键词），返回 top-k 结果。"
    parameters = {"query": "搜索查询，用英文描述你要找的代码功能"}

    def execute(self, **kwargs) -> str:
        query = kwargs.get("query" , "")
        if not query:
            return "Error: query is required"

        dense = DenseRetriever()
        sparse = SparseRetriever.from_redis()

        dense_results = dense.search(query, k=10, where=SYSTEM_CORPUS)
        sparse_results = sparse.search(query, k=10)

        if dense_results and sparse_results:
            fused = rrf([dense_results, sparse_results], top_n=5)
        elif dense_results:
            fused = dense_results[:5]
        elif sparse_results:
            fused = sparse_results[:5]
        else:
            return "No results Found"

        output = []
        for r in fused:
            text = r["text"][:300]
            output.append(f"[{r['source']}]\n{text}\n")
        return "\n---\n".join(output)

class ExplainCode(Tool):
    name = "explain"
    description = "解释 TinyDB 中指定函数或类的功能。结合检索到的代码上下文和 LLM 生成自然语言解释。"
    parameters = {"target": "要解释的函数名或类名，如 'TinyDB' 或 'search'"}

    def execute(self, **kwargs) -> str:
        target = kwargs.get("target" , "")
        if not target:
            return "Error: target is required"

        dense = DenseRetriever()
        results = dense.search(target, k=3, where=SYSTEM_CORPUS)
        if not results:
            return f"Could not find code related to '{target}'"

        context = "\n\n".join([r["text"][:400] for r in results])
        prompt = f"解释下面代码中 '{target}' 的功能：\n\n{context}"
        explanation = call_llm(prompt, system_prompt="你是一个 Python 代码导师，用中文简洁解释代码功能，突出重点。")
        return explanation

class GenerateTest(Tool):
    name = "testgen"
    description = "为 TinyDB 中的指定函数或类生成单元测试代码。先用 search 检索相关代码，再用 LLM 生成 pytest 测试用例。"
    parameters = {"target": "要生成测试的目标函数名或类名，如 'table.search'"}

    def execute(self, **kwargs) -> str:
        target = kwargs.get("target", "")
        if not target:
            return "Error: target is required"

        dense = DenseRetriever()
        results = dense.search(target, k=3, where=SYSTEM_CORPUS)
        if not results:
            return f"Could not find code related to '{target}'"

        context = "\n\n".join([r["text"][:500] for r in results])
        prompt = f"为以下代码中的 '{target}' 编写 pytest 单元测试：\n\n{context}\n\n只输出测试代码，不要解释。"
        test_code = call_llm(prompt, system_prompt="你是一个 Python 测试工程师，输出可直接运行的 pytest 代码。")
        return test_code

AVAILABLE_TOOLS = [SearchCode(), ExplainCode(), GenerateTest()]
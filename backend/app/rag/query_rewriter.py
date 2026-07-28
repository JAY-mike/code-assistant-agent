"""查询改写：HyDE (Hypothetical Document Embedding) 策略"""

import asyncio

from app.agent.llm import call_llm
from app.logger import log

HYDE_SYSTEM_PROMPT = """你是一个 Python 代码助手。用户会问一个关于代码库的问题。
请生成一段你认为最能回答这个问题的 Python 代码片段。
只需要输出代码，不要解释。如果问题不涉及代码，用伪代码表示。"""

EXPAND_SYSTEM_PROMPT = """你是一个搜索优化助手。用户输入一个简短的搜索查询。
请将其扩展为 2-3 个更具体、更可能匹配到相关代码的搜索词。
直接用逗号分隔输出，不要多余解释。"""


async def _save_rewrite_record(original: str, rewritten: str, strategy: str):
    """异步写入 query_rewrites 表（即发即忘，不阻塞调用方）"""
    try:
        from app.database import async_session_factory
        from app.models.query_rewrite import QueryRewrite

        async with async_session_factory() as session:
            session.add(QueryRewrite(
                original_query=original,
                rewritten_query=rewritten,
                strategy=strategy,
            ))
            await session.commit()
    except Exception as e:
        log.warning("Failed to save rewrite record: %s", e)


def hyde_rewrite(query: str) -> str:
    log.info("HyDE rewriting: '%s'", query)
    hypothetical_code = call_llm(query, system_prompt=HYDE_SYSTEM_PROMPT)
    if hypothetical_code:
        log.info("HyDE result: %s...", hypothetical_code[:80])
        return hypothetical_code
    return query


def expand_query(query: str) -> str:
    log.info("Expanding query: '%s'", query)
    expanded = call_llm(query, system_prompt=EXPAND_SYSTEM_PROMPT)
    if expanded:
        log.info("Expanded: %s", expanded)
        return expanded
    return query


async def rewrite(query: str, strategy: str = "hyde") -> str:
    """
    统一的查询改写入口（异步，通过 to_thread 避免阻塞事件循环）

    缓存说明：
    - reranker 缓存键基于改写后的 query 文本，相同改写结果会命中缓存
    - 若要缓存"原始查询→改写结果"的映射，需调用方自行管理
    """
    # ① 将同步的 LLM 调用扔到线程池，不阻塞事件循环
    if strategy == "hyde":
        result = await asyncio.to_thread(hyde_rewrite, query)
    elif strategy == "expand":
        result = await asyncio.to_thread(expand_query, query)
    else:
        result = query

    # ② 粗细粒度的"是否改写"检测：去掉首尾空白后比较
    if result.strip() != query.strip() and result != query:
        asyncio.create_task(_save_rewrite_record(query, result, strategy))

    return result
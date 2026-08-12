"""Agent 对话接口"""

import asyncio
import json
import threading
import time
from typing import Literal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.agent.harness import AgentCancelled, AgentHarness
from app.models.user import User
from app.auth import get_current_user
from app.config import settings
from app.logger import log
from app.services.conversation_service import (
    get_or_create_conversation, save_message, load_history,
)
from app.rag.knowledge_bases import DEFAULT_KNOWLEDGE_BASE

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default="default", min_length=1, max_length=55)
    knowledge_base: Literal["tinydb", "project"] = DEFAULT_KNOWLEDGE_BASE


class TraceStep(BaseModel):
    step: int
    tool_name: str
    arguments: dict | None = None
    status: str
    observation: str | None = None
    citations: list[dict] = Field(default_factory=list)


class Citation(BaseModel):
    knowledge_base: Literal["tinydb", "project"]
    source: str
    excerpt: str


class PerformanceMetrics(BaseModel):
    server_e2e_latency_ms: float
    agent_latency_ms: float
    coordinator_llm_latency_ms: float
    tool_latency_ms: float
    coordinator_llm_call_count: int
    tool_call_count: int
    time_to_first_token_ms: float | None = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    trace: list[TraceStep]
    citations: list[Citation] = Field(default_factory=list)
    metrics: PerformanceMetrics


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _with_knowledge_base(citations: list[dict], knowledge_base: str) -> list[dict]:
    return [{"knowledge_base": knowledge_base, **citation} for citation in citations]


def _performance_metrics(
    harness: AgentHarness,
    started_at: float,
    time_to_first_token_ms: float | None = None,
) -> dict:
    agent_metrics = getattr(harness, "metrics", {})
    return {
        "server_e2e_latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "agent_latency_ms": agent_metrics.get("agent_latency_ms", 0.0),
        "coordinator_llm_latency_ms": agent_metrics.get("coordinator_llm_latency_ms", 0.0),
        "tool_latency_ms": agent_metrics.get("tool_latency_ms", 0.0),
        "coordinator_llm_call_count": agent_metrics.get("coordinator_llm_call_count", 0),
        "tool_call_count": agent_metrics.get("tool_call_count", 0),
        "time_to_first_token_ms": time_to_first_token_ms,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    started_at = time.perf_counter()
    user_id = current_user.id
    scoped_session_id = f"{req.knowledge_base}:{req.session_id}"

    # 1. 确保会话记录存在（按用户隔离）
    await get_or_create_conversation(user_id, scoped_session_id)

    # 2. 从 MySQL 恢复历史（只查当前用户的）
    history = await load_history(user_id, scoped_session_id)
    harness = AgentHarness(
        session_id=scoped_session_id,
        knowledge_base_id=req.knowledge_base,
    )
    harness.restore_history(history)

    # 3. 运行 Agent
    try:
        answer = await asyncio.wait_for(
            asyncio.to_thread(harness.run, req.message),
            timeout=settings.AGENT_REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        answer = (
            "本轮处理超过服务时间预算，未能生成完整回答。"
            "请缩小问题范围后重试。"
        )

    # 4. 保存本轮消息（归属当前用户）
    await save_message(user_id, scoped_session_id, "user", req.message)
    await save_message(user_id, scoped_session_id, "assistant", answer)

    return ChatResponse(
        answer=answer,
        session_id=req.session_id,
        trace=harness.execution_trace,
        citations=_with_knowledge_base(harness.citations, req.knowledge_base),
        metrics=_performance_metrics(harness, started_at),
    )


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    started_at = time.perf_counter()
    first_token_at = None
    user_id = current_user.id
    scoped_session_id = f"{req.knowledge_base}:{req.session_id}"
    await get_or_create_conversation(user_id, scoped_session_id)
    history = await load_history(user_id, scoped_session_id)
    harness = AgentHarness(
        session_id=scoped_session_id,
        knowledge_base_id=req.knowledge_base,
    )
    harness.restore_history(history)

    loop = asyncio.get_running_loop()
    events = asyncio.Queue()
    cancel_event = threading.Event()

    def emit(event: str, data: dict):
        nonlocal first_token_at
        if event == "delta" and first_token_at is None:
            first_token_at = (time.perf_counter() - started_at) * 1000
        loop.call_soon_threadsafe(events.put_nowait, (event, data))

    async def run_agent():
        try:
            answer = await asyncio.to_thread(
                harness.run,
                req.message,
                emit=emit,
                stream_final=True,
                cancel_event=cancel_event,
            )
            await save_message(user_id, scoped_session_id, "user", req.message)
            await save_message(user_id, scoped_session_id, "assistant", answer)
            emit("done", {
                "session_id": req.session_id,
                "citations": _with_knowledge_base(harness.citations, req.knowledge_base),
                "metrics": _performance_metrics(harness, started_at, first_token_at),
            })
        except AgentCancelled:
            emit("cancelled", {"message": "生成已取消。"})
        except Exception:
            log.exception("Streaming agent execution failed")
            emit("error", {"message": "Agent 执行失败，请稍后重试。"})
        finally:
            loop.call_soon_threadsafe(events.put_nowait, None)

    task = asyncio.create_task(run_agent())

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    cancel_event.set()
                    task.cancel()
                    break
                try:
                    event = await asyncio.wait_for(events.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                if event is None:
                    break
                event_name, data = event
                yield _sse_event(event_name, data)
        finally:
            cancel_event.set()
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

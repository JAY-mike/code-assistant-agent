"""Agent 对话接口"""

import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.agent.harness import AgentHarness
from app.models.user import User
from app.auth import get_current_user
from app.services.conversation_service import (
    get_or_create_conversation, save_message, load_history,
)

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    answer: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    # 1. 确保会话记录存在
    await get_or_create_conversation(req.session_id)

    # 2. 从 MySQL 恢复历史
    history = await load_history(req.session_id)
    harness = AgentHarness(session_id=req.session_id)
    harness.restore_history(history)

    # 3. 运行 Agent
    answer = await asyncio.to_thread(harness.run, req.message)

    # 4. 保存本轮消息
    await save_message(req.session_id, "user", req.message)
    await save_message(req.session_id, "assistant", answer)

    return ChatResponse(answer=answer, session_id=req.session_id)

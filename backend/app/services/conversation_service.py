"""会话持久化服务：Agent 对话历史的保存与恢复"""

from sqlalchemy import select

from app.database import async_session_factory
from app.models.conversation import Conversation, Message


async def get_or_create_conversation(session_id: str) -> Conversation:
    """获取或创建会话记录"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            conv = Conversation(session_id=session_id)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
        return conv


async def save_message(session_id: str, role: str, content: str, tool_calls=None):
    """保存一条消息"""
    async with async_session_factory() as session:
        session.add(Message(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        ))
        await session.commit()


async def load_history(session_id: str, limit: int = 20) -> list[dict]:
    """加载会话历史消息（按时间升序），返回 [{role, content}, ...]"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
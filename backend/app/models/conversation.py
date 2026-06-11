import datetime
from datetime import UTC

from sqlalchemy import Column , Integer , String , DateTime , JSON , Text
from app.database import Base

class Conversation(Base):
    """一次对话session"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True, comment="会话ID")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(UTC),
        onupdate=lambda: datetime.datetime.now(UTC),
        comment="最后更新时间",
    )

class Message(Base):
    """对话中的单条消息"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True, comment="所属会话ID")
    role = Column(String(16), nullable=False, comment="角色: user / assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    tool_calls = Column(JSON, nullable=True, comment="Agent 调用的工具信息（JSON）")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(UTC), comment="发送时间")
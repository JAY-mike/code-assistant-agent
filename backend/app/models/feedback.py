import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class Feedback(Base):
    """用户对Agent回答的反馈(点赞/点踩)"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False, index=True, comment="对应消息ID")
    session_id = Column(String(64), nullable=False, comment="所属会话ID")
    rating = Column(Integer, nullable=False, comment="评分: 1=点赞, -1=点踩")
    comment = Column(Text, nullable=True, comment="用户可选评价文本")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间")
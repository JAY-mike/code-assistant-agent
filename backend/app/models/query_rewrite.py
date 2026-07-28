import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class QueryRewrite(Base):
    """查询改写记录：存原始查询、改写后查询、改写策略"""
    __tablename__ = "query_rewrites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_query = Column(Text, nullable=False, comment="原始查询")
    rewritten_query = Column(Text, nullable=False, comment="改写后查询")
    strategy = Column(String(16), nullable=False, comment="改写策略: hyde / expand")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
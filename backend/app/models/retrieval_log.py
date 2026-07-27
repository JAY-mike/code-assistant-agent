import datetime
from datetime import UTC

from sqlalchemy import Column , Integer , String , Text ,DateTime, JSON, Float
from app.database import Base


class RetrievalLog(Base):
    """检索日志：记录每次 hybrid_search 的完整链路"""
    __tablename__ = "retrieval_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_text = Column(Text, nullable=False, comment="用户原始查询")
    dense_top_k = Column(JSON, nullable=True, comment="Dense 路 top-k 结果")
    sparse_top_k = Column(JSON, nullable=True, comment="Sparse 路 top-k 结果")
    fused_top_n = Column(JSON, nullable=True, comment="RRF 融合后 top-n 结果")
    strategy = Column(String(32), default="hybrid", comment="检索策略")
    total_latency_ms = Column(Float, nullable=True, comment="总耗时（毫秒）")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime
from app.database import Base

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_name = Column(String(128), nullable=False, comment="评估名称，如 'baseline_no_rerank'")
    description = Column(Text, nullable=True, comment="评估描述")
    config = Column(JSON, nullable=False, comment="评估配置：哪些组件开启")
    test_set_size = Column(Integer, nullable=False, comment="测试集查询数量")
    hit_rate = Column(Float, nullable=True, comment="Hit Rate")
    mrr = Column(Float, nullable=True, comment="Mean Reciprocal Rank")
    ndcg = Column(Float, nullable=True, comment="NDCG@k")
    avg_latency_ms = Column(Float, nullable=True, comment="平均检索延迟")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
import datetime
from datetime import UTC
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.database import Base

class IndexVersion(Base):
    """索引版本记录：每次重建索引时插入一条"""
    __tablename__ = "index_versions"

    id = Column(Integer , primary_key=True, autoincrement=True)
    strategy = Column(String(32), comment="分块策略")
    chunk_size = Column(Integer, comment="块大小")
    chunk_overlap = Column(Integer, comment="块重叠")
    file_count = Column(Integer, comment="文件数")
    chunk_count = Column(Integer, comment="块数")
    build_duration_ms = Column(Integer, nullable=True, comment="构建耗时（毫秒）")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
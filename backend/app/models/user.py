"""用户模型"""

import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True, comment="用户名")
    hashed_password = Column(String(128), nullable=False, comment="bcrypt 哈希密码")
    role = Column(String(16), default="user", comment="角色: user / admin")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间")
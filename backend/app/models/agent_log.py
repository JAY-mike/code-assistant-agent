"""Agent 决策日志：记录每次 Agent 运行的每步决策链路"""

import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True, comment="会话ID")
    step_number = Column(Integer, nullable=False, comment="第几步")
    thought = Column(Text, nullable=True, comment="LLM 的思考过程")
    action_name = Column(String(32), nullable=True, comment="调用的工具名")
    action_args = Column(Text, nullable=True, comment="工具参数（JSON）")
    observation = Column(Text, nullable=True, comment="工具返回结果摘要")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
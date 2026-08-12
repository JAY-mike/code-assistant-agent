import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
    )

    # App
    APP_NAME: str = "Code Assistant Agent"
    DEBUG: bool = True

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "123456"
    MYSQL_DATABASE: str = "code_assistant"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_CACHE_TTL: int = 300  # 检索缓存过期时间（秒），默认 5 分钟

    # Chroma
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # 目标代码仓库路径
    REPO_PATH: str = "./data/target_repo"
    # 当前项目源码路径；Docker 环境通过 Compose 挂载为只读目录
    PROJECT_SOURCE_PATH: str = "."

    # Embedding 模型
    # EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # 分块策略
    CHUNK_STRATEGY: str = "recursive"  # recursive / semantic / token
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # LLM
    # LLM_API_ENDPOINT: str = "http://localhost:11434/api/chat"  # Ollama
    LLM_API_ENDPOINT: str = "https://api.deepseek.com/v1/chat/completions"
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_API_KEY: str = ""
    # Agent 受控执行预算：每次用户请求在有限时间内返回。
    AGENT_MAX_STEPS: int = 4
    AGENT_MAX_DURATION_SECONDS: float = 75.0
    AGENT_LLM_TIMEOUT_SECONDS: float = 15.0
    AGENT_LLM_MAX_RETRIES: int = 0
    AGENT_TOOL_LLM_TIMEOUT_SECONDS: float = 12.0
    AGENT_REQUEST_TIMEOUT_SECONDS: float = 80.0
    # LLM_MODEL: str = "gemma:7b"
    # JWT
    JWT_SECRET: str = ""  # 从 .env 读取，禁止硬编码

    def _validate_secrets(self):
        """启动时校验密钥，缺失则拒绝启动，避免用空密钥签发 JWT"""
        if not self.LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY 未配置。请在 .env 中设置，或通过环境变量传入。"
                "禁止用空密钥运行。"
            )
        if len(self.JWT_SECRET) < 32:
            raise ValueError(
                "JWT_SECRET 未配置或太短（至少 32 字符）。请在 .env 中设置，"
                "可用: python -c \"import secrets; print(secrets.token_hex(32))\" 生成。"
            )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 测试场景可通过环境变量跳过校验（比如 CI 用固定测试密钥，或纯逻辑单测）
        if not os.environ.get("SKIP_SECRET_VALIDATION"):
            self._validate_secrets()


settings = Settings()

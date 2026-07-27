from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    # Embedding 模型
    # EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # 分块策略
    CHUNK_STRATEGY: str = "recursive"  # recursive / semantic / token
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
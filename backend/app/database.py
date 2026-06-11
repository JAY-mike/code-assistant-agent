from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession , async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# 异步 MySQL 连接 URL：mysql+aiomysql://user:pass@host:port/db
DATABASE_URL = (
    f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo = settings.DEBUG
)

async_session_factory = async_sessionmaker(
    engine,
    class_= AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    """
    所有ORM类型的基类
    """
    pass

async def get_db():
    """FASTAPI依赖注入：每次请求都创建一个数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()

        except Exception:
            await session.rollback()
            raise

        finally:
            await session.close()



from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import engine, Base
from app.models import Message , Conversation , Feedback

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时执行"""
    print(f"[{settings.APP_NAME}] Start up...")

    # 创建所有表
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB] Tables created successfully")
    except Exception as e:
        print(f"[DB WARNING] Failed to create tables (may already exist): {e}")

    yield

    # 关闭数据库连接
    try:
        await engine.dispose()
        print("[DB] Connection closed")
    except Exception as e:
        print(f"[DB WARNING] Error closing connection: {e}")

app = FastAPI(title=settings.APP_NAME , lifespan=lifespan)

@app.get("/")
async def root():
    return {"message" : f"{settings.APP_NAME} is running!"}

@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status" : "ok"}
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import engine, Base
from app.logger import log
from app.routers.auth_router import router as auth_router
from app.routers.agent_router import router as agent_router
from app.routers.search_router import router as search_router
from app.routers.upload_router import router as upload_router
from app.middleware import RateLimitMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("%s Starting up...", settings.APP_NAME)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Tables created successfully")
    except Exception as e:
        log.warning("Failed to create tables (may already exist): %s", e)

    yield

    try:
        await engine.dispose()
        log.info("Connection closed")
    except Exception as e:
        log.warning("Error closing connection: %s", e)


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.add_middleware(RateLimitMiddleware, rate_limit=60, window_seconds=60)
app.include_router(auth_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} is running!"}


@app.get("/health")
async def health():
    return {"status": "ok"}

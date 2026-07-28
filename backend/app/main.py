from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import engine, Base
from app.logger import log


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


@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} is running!"}


@app.get("/health")
async def health():
    return {"status": "ok"}

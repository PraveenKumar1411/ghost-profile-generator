"""PostgreSQL engine, session, and application lifecycle helpers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.models.scans import Base


settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)
session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create database tables on startup and dispose the pool on shutdown."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        if connection.dialect.name == "postgresql":
            for column in ("facebook", "youtube", "tiktok", "threads", "telegram"):
                await connection.execute(
                    text(
                        f"ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                        f"{column} BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )

    app.state.database_engine = engine
    try:
        yield
    finally:
        await engine.dispose()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield one transaction-scoped database session per request."""

    async with session_factory() as session:
        yield session


async def check_database_connection(request: Request) -> bool:
    """Check whether PostgreSQL is reachable."""

    database_engine = getattr(request.app.state, "database_engine", None)
    if database_engine is None:
        return False

    try:
        async with database_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True

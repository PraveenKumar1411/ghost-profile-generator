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
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "privacy_grade VARCHAR(2) NOT NULL DEFAULT 'A+'"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "report_id VARCHAR(20)"
                )
            )
            await connection.execute(
                text(
                    "UPDATE scans SET report_id = "
                    "'GPG-' || EXTRACT(YEAR FROM COALESCE(created_at, NOW()))::int "
                    "|| '-' || LPAD(id::text, 5, '0') WHERE report_id IS NULL"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ALTER COLUMN report_id SET NOT NULL"
                )
            )
            await connection.execute(
                text(
                    "UPDATE scans SET privacy_grade = CASE "
                    "WHEN risk_score <= 10 THEN 'A+' "
                    "WHEN risk_score <= 20 THEN 'A' "
                    "WHEN risk_score <= 35 THEN 'B' "
                    "WHEN risk_score <= 50 THEN 'C' "
                    "WHEN risk_score <= 70 THEN 'D' ELSE 'F' END"
                )
            )
            await connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_scans_report_id "
                    "ON scans (report_id)"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "recommendations JSON NOT NULL DEFAULT '[]'::json"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "insight VARCHAR(500) NOT NULL DEFAULT ''"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "category_exposure JSON NOT NULL DEFAULT '{}'::json"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "scan_id VARCHAR(24)"
                )
            )
            await connection.execute(
                text(
                    "UPDATE scans SET scan_id = COALESCE(scan_id, report_id) "
                    "WHERE scan_id IS NULL"
                )
            )
            await connection.execute(
                text("ALTER TABLE scans ALTER COLUMN scan_id SET NOT NULL")
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "status VARCHAR(12) NOT NULL DEFAULT 'completed'"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "progress INTEGER NOT NULL DEFAULT 100"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "current_platform VARCHAR(40)"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "failure_reason VARCHAR(500)"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "started_at TIMESTAMPTZ"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS "
                    "completed_at TIMESTAMPTZ"
                )
            )
            await connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_scans_scan_id "
                    "ON scans (scan_id)"
                )
            )
            await connection.execute(
                text("ALTER TABLE scans DROP CONSTRAINT IF EXISTS ck_scans_status")
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD CONSTRAINT ck_scans_status "
                    "CHECK (status IN ('queued', 'running', 'completed', 'failed'))"
                )
            )
            await connection.execute(
                text("ALTER TABLE scans DROP CONSTRAINT IF EXISTS ck_scans_progress")
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD CONSTRAINT ck_scans_progress "
                    "CHECK (progress BETWEEN 0 AND 100)"
                )
            )
            await connection.execute(
                text("ALTER TABLE scans DROP CONSTRAINT IF EXISTS ck_scans_risk_level")
            )
            await connection.execute(
                text("UPDATE scans SET risk_level = 'CRITICAL' WHERE risk_score > 80")
            )
            await connection.execute(
                text(
                    "ALTER TABLE scans ADD CONSTRAINT ck_scans_risk_level "
                    "CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))"
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

"""CRUD operations for persisted scan history."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scans import Scan
from app.schemas.scan import ScanResponse


async def create_scan(
    session: AsyncSession,
    scan_result: ScanResponse,
) -> Scan:
    """Persist a completed scan and return the database entity."""

    scan = Scan(**scan_result.model_dump())
    session.add(scan)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    await session.refresh(scan)
    return scan


async def list_scans(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> Sequence[Scan]:
    """Return scans newest first with bounded pagination."""

    result = await session.execute(
        select(Scan)
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


async def get_scan(session: AsyncSession, scan_id: int) -> Scan | None:
    """Return one persisted scan by primary key."""

    return await session.get(Scan, scan_id)

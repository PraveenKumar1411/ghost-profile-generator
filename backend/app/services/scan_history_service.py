"""CRUD operations for persisted scan history."""

from collections.abc import Sequence

from datetime import datetime
from uuid import uuid4

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

    scan = Scan(
        **scan_result.model_dump(
            exclude={
                "report_id",
                "previous_risk_score",
                "recommendations",
                "insight",
                "category_exposure",
                "verification_status",
                "verification_reasons",
            }
        ),
        report_id=f"tmp-{uuid4().hex[:12]}",
        scan_id=f"tmp-{uuid4().hex[:12]}",
        status="completed",
        progress=100,
        completed_at=datetime.now().astimezone(),
        recommendations=scan_result.recommendations,
        insight=scan_result.insight,
        category_exposure=scan_result.category_exposure,
        verification_status=scan_result.verification_status,
        verification_reasons=scan_result.verification_reasons,
    )
    session.add(scan)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    scan.report_id = f"GPG-{datetime.now().year}-{scan.id:05d}"
    scan.scan_id = scan.report_id
    await session.commit()
    await session.refresh(scan)
    return scan


async def create_scan_job(session: AsyncSession, username: str) -> Scan:
    """Create and persist a queued asynchronous scan job."""

    scan = Scan(
        username=username,
        github=False,
        reddit=False,
        twitter=False,
        instagram=False,
        linkedin=False,
        facebook=False,
        youtube=False,
        tiktok=False,
        threads=False,
        telegram=False,
        verification_status={},
        verification_reasons={},
        risk_score=0,
        risk_level="LOW",
        privacy_grade="A+",
        report_id=f"tmp-{uuid4().hex[:12]}",
        scan_id=f"tmp-{uuid4().hex[:12]}",
        status="queued",
        progress=0,
    )
    session.add(scan)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    scan.scan_id = f"GPG-{datetime.now().year}-{scan.id:05d}"
    scan.report_id = scan.scan_id
    await session.commit()
    await session.refresh(scan)
    return scan


async def get_scan_by_scan_id(session: AsyncSession, scan_id: str) -> Scan | None:
    """Return a scan job by its public scan identifier."""

    result = await session.execute(select(Scan).where(Scan.scan_id == scan_id))
    return result.scalar_one_or_none()


async def update_scan_job(
    session: AsyncSession,
    scan_id: str,
    **values: object,
) -> Scan | None:
    """Update job state and return the refreshed entity."""

    scan = await get_scan_by_scan_id(session, scan_id)
    if scan is None:
        return None
    for field, value in values.items():
        setattr(scan, field, value)
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


async def get_scan_by_report_id(
    session: AsyncSession,
    report_id: str,
) -> Scan | None:
    """Return a persisted scan by its public report identifier."""

    result = await session.execute(select(Scan).where(Scan.report_id == report_id))
    return result.scalar_one_or_none()


async def get_latest_scan_for_username(
    session: AsyncSession,
    username: str,
) -> Scan | None:
    """Return the newest persisted scan for a username."""

    result = await session.execute(
        select(Scan)
        .where(Scan.username == username)
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_scan_analytics(session: AsyncSession) -> dict[str, object]:
    """Return aggregate scan metrics for the analytics dashboard."""

    scans = list(await list_scans(session, limit=100, offset=0))
    if not scans:
        return {
            "total_scans": 0,
            "highest_risk_score": 0,
            "average_risk_score": 0,
            "most_common_platform": None,
            "recent_activity": [],
        }
    platform_fields = (
        "github", "reddit", "twitter", "instagram", "linkedin",
        "facebook", "youtube", "tiktok", "threads", "telegram",
    )
    counts = {
        platform: sum(bool(getattr(scan, platform)) for scan in scans)
        for platform in platform_fields
    }
    return {
        "total_scans": len(scans),
        "highest_risk_score": max(scan.risk_score for scan in scans),
        "average_risk_score": round(sum(scan.risk_score for scan in scans) / len(scans), 1),
        "most_common_platform": max(counts, key=counts.get),
        "recent_activity": [
            {"report_id": scan.report_id, "username": scan.username, "risk_score": scan.risk_score}
            for scan in scans[:5]
        ],
    }

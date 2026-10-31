"""Persisted scan history routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.schemas.scan_history import ScanHistoryResponse
from app.services.scan_history_service import (
    get_scan,
    get_scan_analytics,
    list_scans,
)

router = APIRouter(prefix="/scans", tags=["scan history"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "",
    response_model=list[ScanHistoryResponse],
    summary="List persisted scans",
)
async def get_scans(
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ScanHistoryResponse]:
    """Return recent scans using bounded offset pagination."""

    return list(await list_scans(session, limit=limit, offset=offset))


@router.get(
    "/{scan_id}",
    response_model=ScanHistoryResponse,
    summary="Get a persisted scan",
)
async def get_scan_by_id(
    session: DatabaseSession,
    scan_id: Annotated[int, Path(ge=1)],
) -> ScanHistoryResponse:
    """Return one persisted scan by ID."""

    scan = await get_scan(session, scan_id)
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )
    return scan


@router.get(
    "/analytics/summary",
    summary="Return aggregate scan analytics",
)
async def get_analytics(session: DatabaseSession) -> dict[str, object]:
    """Return dashboard metrics for persisted scans."""

    return await get_scan_analytics(session)

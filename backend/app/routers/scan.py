"""Username scan routes."""

import re

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.schemas.scan import (
    ScanJobResult,
    ScanRequest,
    ScanResponse,
    ScanStartResponse,
    ScanStatusResponse,
)
from app.services.risk_service import (
    calculate_privacy_grade,
    calculate_risk,
    category_presence,
    insight_for,
    recommendations_for,
)
from app.services.scan_history_service import (
    create_scan,
    create_scan_job,
    get_latest_scan_for_username,
    get_scan_by_scan_id,
)
from app.services.scan_job_service import get_job_snapshot, run_scan_job
from app.services.scan_service import (
    SherlockTimeoutError,
    SherlockUnavailableError,
    scan_username,
)

router = APIRouter(prefix="/scan", tags=["scan"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,38}$")
PLATFORM_LABELS = {
    "github": "GitHub",
    "reddit": "Reddit",
    "twitter": "Twitter",
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "facebook": "Facebook",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "threads": "Threads",
    "telegram": "Telegram",
}


def _validate_username(username: str) -> str:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty",
        )
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Username must contain 1-39 letters, numbers, underscores, "
                "periods, or hyphens and must start with a letter, number, "
                "or underscore"
            ),
        )
    return normalized_username


@router.post(
    "/start",
    response_model=ScanStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an asynchronous scan",
)
async def start_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    session: DatabaseSession,
) -> ScanStartResponse:
    """Create a queued scan and return without waiting for Sherlock."""

    username = _validate_username(request.username)
    scan = await create_scan_job(session, username)
    background_tasks.add_task(run_scan_job, scan.scan_id, username)
    return ScanStartResponse(scan_id=scan.scan_id, status=scan.status)


@router.get(
    "/status/{scan_id}",
    response_model=ScanStatusResponse,
    summary="Get asynchronous scan progress",
)
async def scan_status(scan_id: str) -> ScanStatusResponse:
    """Return the latest durable progress checkpoint for a scan."""

    snapshot = await get_job_snapshot(scan_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return ScanStatusResponse(**snapshot)


@router.get(
    "/result/{scan_id}",
    response_model=ScanJobResult,
    summary="Get completed asynchronous scan result",
)
async def scan_result(scan_id: str, session: DatabaseSession) -> ScanJobResult:
    """Return the completed scan result for a job."""

    scan = await get_scan_by_scan_id(session, scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    if scan.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scan is {scan.status}",
        )
    platforms_found = [
        label
        for field, label in PLATFORM_LABELS.items()
        if getattr(scan, field)
    ]
    return ScanJobResult(
        scan_id=scan.scan_id,
        status=scan.status,
        progress=scan.progress,
        current_platform=scan.current_platform,
        completed_platforms=list(platforms_found),
        remaining_platforms=[],
        failure_reason=scan.failure_reason,
        username=scan.username,
        risk_score=scan.risk_score,
        risk_level=scan.risk_level,
        privacy_grade=scan.privacy_grade,
        platforms_found=platforms_found,
        recommendations=scan.recommendations,
        report_id=scan.report_id,
        insight=scan.insight,
        verification_status=scan.verification_status or {},
        verification_reasons=scan.verification_reasons or {},
    )


@router.get(
    "/{username}",
    response_model=ScanResponse,
    summary="Generate a digital footprint analysis",
)
async def scan(username: str, session: DatabaseSession) -> ScanResponse:
    """Scan a username and calculate its digital-footprint risk."""

    normalized_username = _validate_username(username)

    try:
        scan_result = await scan_username(normalized_username)
    except SherlockTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except SherlockUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    risk_score, risk_level = calculate_risk(scan_result)
    previous_scan = await get_latest_scan_for_username(session, normalized_username)
    response = ScanResponse(
        username=normalized_username,
        **scan_result,
        risk_score=risk_score,
        risk_level=risk_level,
        previous_risk_score=previous_scan.risk_score if previous_scan else None,
        privacy_grade=calculate_privacy_grade(risk_score),
        recommendations=recommendations_for(risk_level),
        insight=insight_for(scan_result, risk_level),
        category_exposure=category_presence(scan_result),
    )
    persisted_scan = await create_scan(session, response)
    response.report_id = persisted_scan.report_id
    return response

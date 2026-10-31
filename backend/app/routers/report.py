"""PDF report routes."""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.reports.pdf_generator import generate_pdf_report
from app.schemas.scan import ScanResponse
from app.services.risk_service import (
    calculate_privacy_grade,
    calculate_risk,
    category_presence,
    insight_for,
    recommendations_for,
)
from app.services.scan_history_service import (
    get_latest_scan_for_username,
    get_scan_by_report_id,
)
from app.services.scan_service import (
    SherlockTimeoutError,
    SherlockUnavailableError,
    scan_username,
)

router = APIRouter(prefix="/report", tags=["report"])

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,38}$")


@router.get(
    "/{username}",
    response_class=Response,
    summary="Download a digital footprint PDF report",
)
async def report(
    username: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Generate and return a PDF report for a username scan."""

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
    persisted_scan = await get_latest_scan_for_username(session, normalized_username)
    scan = ScanResponse(
        username=normalized_username,
        **scan_result,
        risk_score=risk_score,
        risk_level=risk_level,
        privacy_grade=calculate_privacy_grade(risk_score),
        report_id=persisted_scan.report_id if persisted_scan else None,
        recommendations=recommendations_for(risk_level),
        insight=insight_for(scan_result, risk_level),
        category_exposure=category_presence(scan_result),
    )
    pdf = generate_pdf_report(scan, scan_date=datetime.now().astimezone())
    filename = f"ghost-profile-{normalized_username}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/id/{report_id}",
    response_class=Response,
    summary="Download a report by report ID",
)
async def report_by_id(
    report_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Download the exact persisted scan associated with a report ID."""

    persisted_scan = await get_scan_by_report_id(session, report_id)
    if persisted_scan is None:
        raise HTTPException(status_code=404, detail="Report not found")
    scan = ScanResponse.model_validate(persisted_scan)
    pdf = generate_pdf_report(scan, scan_date=persisted_scan.created_at)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{report_id}.pdf"',
        },
    )

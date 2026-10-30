"""PDF report routes."""

import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.reports.pdf_generator import generate_pdf_report
from app.schemas.scan import ScanResponse
from app.services.risk_service import calculate_risk
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
async def report(username: str) -> Response:
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
    scan = ScanResponse(
        username=normalized_username,
        **scan_result,
        risk_score=risk_score,
        risk_level=risk_level,
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

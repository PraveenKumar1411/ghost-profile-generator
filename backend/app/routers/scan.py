"""Username scan routes."""

import re

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.schemas.scan import ScanResponse
from app.services.risk_service import calculate_risk
from app.services.scan_history_service import create_scan
from app.services.scan_service import (
    SherlockTimeoutError,
    SherlockUnavailableError,
    scan_username,
)

router = APIRouter(prefix="/scan", tags=["scan"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,38}$")


@router.get(
    "/{username}",
    response_model=ScanResponse,
    summary="Generate a digital footprint analysis",
)
async def scan(username: str, session: DatabaseSession) -> ScanResponse:
    """Scan a username and calculate its digital-footprint risk."""

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
    response = ScanResponse(
        username=normalized_username,
        **scan_result,
        risk_score=risk_score,
        risk_level=risk_level,
    )
    await create_scan(session, response)
    return response

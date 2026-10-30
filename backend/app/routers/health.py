"""Health check routes."""

from fastapi import APIRouter, Request

from app.models.health import HealthResponse
from app.services.health_service import get_health

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API and database health",
)
async def health_check(request: Request) -> HealthResponse:
    """Return the current API and PostgreSQL health status."""

    return await get_health(request)

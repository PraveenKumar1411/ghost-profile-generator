"""Health check business logic."""

from fastapi import Request

from app.config import get_settings
from app.database import check_database_connection
from app.models.health import HealthResponse


async def get_health(request: Request) -> HealthResponse:
    """Build the service health response."""

    database_connected = await check_database_connection(request)
    return HealthResponse(
        status="ok" if database_connected else "degraded",
        service=get_settings().app_name,
        database="connected" if database_connected else "unavailable",
    )

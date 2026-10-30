"""Health check response models."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response returned by the service health endpoint."""

    status: Literal["ok", "degraded"]
    service: str
    database: Literal["connected", "unavailable"]
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

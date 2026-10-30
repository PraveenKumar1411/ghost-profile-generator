"""Standard API error response models."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Stable error shape returned by the API."""

    detail: str
    request_id: str | None = None

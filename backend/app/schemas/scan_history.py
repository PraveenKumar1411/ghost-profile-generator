"""Schemas for persisted scan history responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class ScanHistoryResponse(BaseModel):
    """A persisted scan returned by the history API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    github: bool
    reddit: bool
    twitter: bool
    instagram: bool
    linkedin: bool
    facebook: bool
    youtube: bool
    tiktok: bool
    threads: bool
    telegram: bool
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    created_at: datetime

"""Schemas for username scans."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class ScanRequest(BaseModel):
    """Input contract for a username scan."""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=1, max_length=39)


class ScanResponse(BaseModel):
    """Digital footprint and risk assessment for a username."""

    username: str
    github: bool
    reddit: bool
    twitter: bool
    instagram: bool
    linkedin: bool
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel

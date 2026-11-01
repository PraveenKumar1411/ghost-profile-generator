"""Schemas for username scans."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
PrivacyGrade = Literal["A+", "A", "B", "C", "D", "F"]
VerificationStatus = Literal["FOUND", "NOT_FOUND", "UNVERIFIED", "BLOCKED"]


class ScanRequest(BaseModel):
    """Input contract for a username scan."""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=1, max_length=39)


class ScanStartResponse(BaseModel):
    """Immediate acknowledgement for an asynchronous scan job."""

    scan_id: str
    status: Literal["queued", "running", "completed", "failed"]


class ScanStatusResponse(BaseModel):
    """Live status for an asynchronous scan job."""

    scan_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int = Field(ge=0, le=100)
    current_platform: str | None = None
    completed_platforms: list[str] = Field(default_factory=list)
    remaining_platforms: list[str] = Field(default_factory=list)
    failure_reason: str | None = None


class ScanJobResult(ScanStatusResponse):
    """Completed scan result returned by the asynchronous result endpoint."""

    username: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    privacy_grade: PrivacyGrade
    platforms_found: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    report_id: str
    insight: str = ""
    verification_status: dict[str, VerificationStatus] = Field(default_factory=dict)
    verification_reasons: dict[str, str] = Field(default_factory=dict)


class ScanResponse(BaseModel):
    """Digital footprint and risk assessment for a username."""

    model_config = ConfigDict(from_attributes=True)

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
    privacy_grade: PrivacyGrade
    report_id: str | None = None
    previous_risk_score: int | None = None
    recommendations: list[str] = Field(default_factory=list)
    insight: str = ""
    category_exposure: dict[str, bool] = Field(default_factory=dict)
    verification_status: dict[str, VerificationStatus] = Field(default_factory=dict)
    verification_reasons: dict[str, str] = Field(default_factory=dict)

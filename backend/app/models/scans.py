"""SQLAlchemy model for persisted username scans."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Scan(Base):
    """A completed digital-footprint scan."""

    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_scans_risk_score"),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_scans_risk_level",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_scans_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_scans_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(39), nullable=False, index=True)
    github: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reddit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    twitter: Mapped[bool] = mapped_column(Boolean, nullable=False)
    instagram: Mapped[bool] = mapped_column(Boolean, nullable=False)
    linkedin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    facebook: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    youtube: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tiktok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    threads: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    privacy_grade: Mapped[str] = mapped_column(String(2), nullable=False, default="A+")
    report_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    scan_id: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="completed")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    current_platform: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    insight: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    category_exposure: Mapped[dict[str, bool]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

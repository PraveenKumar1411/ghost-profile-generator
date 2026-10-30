"""SQLAlchemy model for persisted username scans."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Scan(Base):
    """A completed digital-footprint scan."""

    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_scans_risk_score"),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_scans_risk_level",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(39), nullable=False, index=True)
    github: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reddit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    twitter: Mapped[bool] = mapped_column(Boolean, nullable=False)
    instagram: Mapped[bool] = mapped_column(Boolean, nullable=False)
    linkedin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

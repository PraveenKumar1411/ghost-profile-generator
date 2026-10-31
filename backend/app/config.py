"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API."""

    app_name: str = "Ghost Profile Generator API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    sherlock_request_timeout: int = Field(
        default=30,
        alias="SHERLOCK_REQUEST_TIMEOUT",
        ge=1,
        le=120,
    )

    sherlock_process_timeout: int = Field(
        default=180,
        alias="SHERLOCK_PROCESS_TIMEOUT",
        ge=1,
        le=600,
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5433/ghost_profile_generator",
        alias="DATABASE_URL",
    )

    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "https://ghost-profile-generator.vercel.app",
        ],
        alias="CORS_ORIGINS",
    )

    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the process."""
    return Settings()
"""Application settings for the synchronous, stateless Vercel backend.

Every setting is read from the environment with the ``APP_`` prefix.
Secrets have no default; they come from the environment only.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "prod", "test"]


class _Group(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class LimitsSettings(_Group):
    """Request limits served by GET /api/v1/tools as UI hints; enforced server-side."""

    max_request_bytes: int = Field(
        # Vercel Functions reject request bodies above 4.5 MB before the app runs.
        default=4_500_000,
        ge=1024,
        description="Maximum request body size in bytes.",
    )
    max_pages: int = Field(
        default=100,
        ge=1,
        description="Maximum pages per PDF document.",
    )


class RateLimitSettings(_Group):
    """Per-IP rate limiting (in-memory, best-effort, no state storage)."""

    enabled: bool = Field(
        default=True,
        description="Enable rate limiting.",
    )
    per_ip_per_minute: int = Field(
        default=60,
        ge=1,
        description="Requests allowed per IP per minute.",
    )


class Settings(BaseSettings):
    """Parsed environment variables. Raises on validation failure at import."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        # Ignore unknown APP_* variables (e.g. ones set by the hosting platform or
        # older deployments) instead of crashing the whole app at startup.
        extra="ignore",
    )

    environment: Environment = Field(
        default="dev",
        description="Deployment environment (local, dev, prod, test).",
    )
    groq_api_key: SecretStr | None = Field(
        default=None,
        description="Groq API key for AI features. Optional in Phase 1 (coming-soon tools only).",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat model used by the AI tools.",
    )
    limits: LimitsSettings = Field(default_factory=LimitsSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ("local", "dev", "prod", "test"):
            raise ValueError(f"Invalid environment: {v}")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once from environment. Raises on validation failure."""
    return Settings()

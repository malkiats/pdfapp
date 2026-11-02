"""Application settings for the synchronous, stateless Vercel backend.

Every setting is read from the environment with the ``APP_`` prefix.
Secrets have no default; they come from the environment only.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "prod", "test"]


class _Group(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LimitsSettings(_Group):
    """Request limits served by GET /api/v1/tools as UI hints; enforced server-side."""

    max_request_bytes: int = Field(
        default=26214400,  # 25 MB
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
        extra="forbid",
    )

    environment: Environment = Field(
        default="dev",
        description="Deployment environment (local, dev, prod, test).",
    )
    groq_api_key: SecretStr | None = Field(
        default=None,
        description="Groq API key for AI features. Optional in Phase 1 (coming-soon tools only).",
    )
    limits: LimitsSettings = Field(default_factory=LimitsSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ("local", "dev", "prod", "test"):
            raise ValueError(f"Invalid environment: {v}")
        return v

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> Settings:  # type: ignore[override]
        """Override to handle both dict and Settings objects."""
        if isinstance(obj, Settings):
            return obj
        return super().model_validate(obj, **kwargs)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once from environment. Raises on validation failure."""
    return Settings()

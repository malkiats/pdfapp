"""Application settings for the synchronous, stateless Vercel backend.

Every setting is read from the environment with the ``APP_`` prefix.
Secrets have no default; they come from the environment only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "prod", "test"]

DEFAULT_PRESIGN_EXPIRES: Final = 900
MIN_PRESIGN_EXPIRES: Final = 60
MAX_PRESIGN_EXPIRES: Final = 3600
_PREFIX_RE: Final = re.compile(r"[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*")
_ACCOUNT_RE: Final = re.compile(r"[A-Za-z0-9]{1,64}")
_R2_HOST_RE: Final = re.compile(r"[a-z0-9]{1,64}(\.(eu|fedramp))?\.r2\.cloudflarestorage\.com")


@dataclass(frozen=True)
class R2Config:
    """Resolved Cloudflare R2 settings. The secret stays a SecretStr (never printed)."""

    access_key_id: str
    secret_access_key: SecretStr
    bucket: str
    endpoint: str
    prefix: str
    presign_expires: int

    def __repr__(self) -> str:  # never leak the key id or secret in tracebacks
        return "R2Config(<redacted>)"


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
    inline_max_bytes: int = Field(
        # Leaves room for multipart framing under max_request_bytes.
        default=4_194_304,
        ge=1,
        description="Largest total file size the inline multipart flow accepts.",
    )
    max_large_file_bytes: int = Field(
        default=100 * 1024 * 1024,
        ge=1,
        description="Large-file flow: maximum size of one file.",
    )
    max_large_total_bytes: int = Field(
        default=250 * 1024 * 1024,
        ge=1,
        description="Large-file flow: maximum total size of one upload (also caps the result).",
    )
    max_large_pages: int = Field(
        default=2000,
        ge=1,
        description="Large-file flow: maximum pages per PDF document.",
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
    uploads_per_ip_per_minute: int = Field(
        default=5,
        ge=1,
        description="createUpload and runUploadedTool calls allowed per IP per minute (each).",
    )


class Settings(BaseSettings):
    """Parsed environment variables. Raises on validation failure at import."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        # Ignore unknown APP_* variables (e.g. ones set by the hosting platform or
        # older deployments) instead of crashing the whole app at startup.
        extra="ignore",
        # R2_* use un-prefixed aliases; tests and code may still pass field names.
        populate_by_name=True,
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

    # ---- Cloudflare R2 (large-file flow). Un-prefixed names, as set in Vercel. ----
    r2_access_key_id: str | None = Field(default=None, validation_alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: SecretStr | None = Field(
        default=None, validation_alias="R2_SECRET_ACCESS_KEY"
    )
    r2_account_id: str | None = Field(default=None, validation_alias="R2_ACCOUNT_ID")
    r2_bucket_name: str | None = Field(default=None, validation_alias="R2_BUCKET_NAME")
    r2_endpoint: str | None = Field(default=None, validation_alias="R2_ENDPOINT")
    r2_presign_expires: int = Field(
        default=DEFAULT_PRESIGN_EXPIRES,
        validation_alias="R2_PRESIGN_EXPIRES",
        description="Presigned URL lifetime in seconds; empty means 900, clamped to 60..3600.",
    )
    r2_prefix: str = Field(default="pdfapp", validation_alias="R2_PREFIX")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ("local", "dev", "prod", "test"):
            raise ValueError(f"Invalid environment: {v}")
        return v

    @field_validator(
        "r2_access_key_id", "r2_account_id", "r2_bucket_name", "r2_endpoint", mode="before"
    )
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("r2_secret_access_key", mode="before")
    @classmethod
    def _blank_secret_is_unset(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        if isinstance(v, SecretStr) and not v.get_secret_value().strip():
            return None
        return v

    @field_validator("r2_presign_expires", mode="before")
    @classmethod
    def _presign_expires(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return DEFAULT_PRESIGN_EXPIRES
        try:
            seconds = int(str(v).strip())
        except ValueError:
            raise ValueError("R2_PRESIGN_EXPIRES must be a whole number of seconds") from None
        return max(MIN_PRESIGN_EXPIRES, min(MAX_PRESIGN_EXPIRES, seconds))

    @field_validator("r2_prefix", mode="before")
    @classmethod
    def _prefix(cls, v: object) -> str:
        prefix = str(v or "").strip().strip("/") or "pdfapp"
        if len(prefix) > 128 or not _PREFIX_RE.fullmatch(prefix):
            raise ValueError("R2_PREFIX must be path segments of A-Z a-z 0-9 _ -")
        return prefix

    @field_validator("r2_endpoint")
    @classmethod
    def _endpoint(cls, v: str | None) -> str | None:
        if v is None:
            return None
        parsed = urlsplit(v)
        local = parsed.hostname in ("127.0.0.1", "localhost")
        if not parsed.hostname or not (
            parsed.scheme == "https" or (parsed.scheme == "http" and local)
        ):
            raise ValueError("R2_ENDPOINT must be an https URL")
        if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("R2_ENDPOINT must be the bare account endpoint")
        if parsed.username or parsed.password:
            raise ValueError("R2_ENDPOINT must not contain credentials")
        return f"{parsed.scheme}://{parsed.netloc}"

    @model_validator(mode="after")
    def _deployed_r2_rules(self) -> Settings:
        """Outside local/test the endpoint must be a real R2 host (no custom host, port or
        plain http), and every object must live under pdfapp/."""
        if self.environment in ("local", "test"):
            return self
        if self.r2_endpoint is not None:
            parsed = urlsplit(self.r2_endpoint)
            host = parsed.hostname or ""
            if (
                parsed.scheme != "https"
                or parsed.port is not None
                or not _R2_HOST_RE.fullmatch(host)
            ):
                raise ValueError(
                    "R2_ENDPOINT must be https://<account>.r2.cloudflarestorage.com "
                    "(optionally .eu. or .fedramp.), without a port"
                )
        # The bucket is shared with another product: never operate outside pdfapp/.
        if not (self.r2_prefix == "pdfapp" or self.r2_prefix.startswith("pdfapp/")):
            raise ValueError('R2_PREFIX must be "pdfapp" or start with "pdfapp/"')
        return self

    def r2(self) -> R2Config | None:
        """The R2 configuration, or None when a required variable is missing."""
        endpoint = self.r2_endpoint or (
            f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
            if self.r2_account_id and _ACCOUNT_RE.fullmatch(self.r2_account_id)
            else None
        )
        if not (
            self.r2_access_key_id and self.r2_secret_access_key and self.r2_bucket_name and endpoint
        ):
            return None
        return R2Config(
            access_key_id=self.r2_access_key_id,
            secret_access_key=self.r2_secret_access_key,
            bucket=self.r2_bucket_name,
            endpoint=endpoint,
            prefix=self.r2_prefix,
            presign_expires=self.r2_presign_expires,
        )

    @property
    def large_files_enabled(self) -> bool:
        return self.r2() is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once from environment. Raises on validation failure."""
    return Settings()

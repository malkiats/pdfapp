from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from pdfapp.backend.app.core.config import Settings


def test_defaults_are_safe_and_complete() -> None:
    s = Settings()
    assert s.env == "local"
    assert s.redis.url is None
    assert s.security.ip_hash_key is None
    assert s.storage.backend == "local"
    assert s.cors.allowed_origins == ["http://localhost:3000"]
    assert s.limits.free.max_file_bytes == 25 * 1024 * 1024
    assert s.limits.free.max_files_per_job == 5
    assert s.limits.pro.max_file_bytes == 250 * 1024 * 1024
    assert s.retention.output_ttl_seconds == 3600
    assert s.retention.delivered_grace_seconds == 120
    assert s.retention.hard_ttl_seconds == 7200
    assert s.retention.sweep_interval_seconds == 300
    assert s.plans.personal.amount == Decimal("2.99")
    assert s.plans.pro.amount == Decimal("5.99")
    assert s.plans.pro.currency == "USD"
    assert s.queues.docs == ["docs"]


def test_nested_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APP_REDIS__URL", "redis://redis:6379/0")
    monkeypatch.setenv(
        "APP_CORS__ALLOWED_ORIGINS", "https://app.example.com, http://localhost:3000"
    )
    monkeypatch.setenv("APP_LIMITS__FREE__MAX_FILE_BYTES", "1048576")
    monkeypatch.setenv("APP_PLANS__PRO__AMOUNT", "7.49")
    monkeypatch.setenv("APP_QUEUES__DOCS", '["docs-paid", "docs"]')
    s = Settings()
    assert s.env == "dev"
    assert s.redis.url is not None
    assert s.redis.url.get_secret_value() == "redis://redis:6379/0"
    assert s.cors.allowed_origins == ["https://app.example.com", "http://localhost:3000"]
    assert s.limits.free.max_file_bytes == 1048576
    assert s.limits.free.max_files_per_job == 5  # untouched sibling keeps its default
    assert s.plans.pro.amount == Decimal("7.49")
    assert s.queues.docs == ["docs-paid", "docs"]


def test_json_list_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS__ALLOWED_ORIGINS", '["https://a.example.com"]')
    assert Settings().cors.allowed_origins == ["https://a.example.com"]


def test_secrets_are_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_REDIS__URL", "redis://:hunter2-canary@redis:6379/0")
    monkeypatch.setenv("APP_SECURITY__IP_HASH_KEY", "k" * 40)
    s = Settings()
    assert "hunter2-canary" not in repr(s)
    assert "k" * 40 not in repr(s)


@pytest.mark.parametrize(
    "origin", ["*", "https://*.example.com", "https://app.example.com/path", "ftp://x.example"]
)
def test_rejects_wildcard_or_malformed_origins(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv("APP_CORS__ALLOWED_ORIGINS", origin)
    with pytest.raises(ValidationError):
        Settings()


def test_prod_requires_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(ValidationError) as info:
        Settings()
    text = str(info.value)
    assert "APP_REDIS__URL" in text
    assert "APP_SECURITY__IP_HASH_KEY" in text
    assert "APP_CORS__ALLOWED_ORIGINS" in text


def test_prod_requires_https_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_REDIS__URL", "rediss://redis:6379/0")
    monkeypatch.setenv("APP_SECURITY__IP_HASH_KEY", "x" * 48)
    monkeypatch.setenv("APP_CORS__ALLOWED_ORIGINS", "http://app.example.com")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("APP_CORS__ALLOWED_ORIGINS", "https://app.example.com")
    assert Settings().is_prod


def test_short_ip_hash_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECURITY__IP_HASH_KEY", "short")
    with pytest.raises(ValidationError):
        Settings()


def test_retention_ordering_and_unknown_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_RETENTION__OUTPUT_TTL_SECONDS", "9000")
    with pytest.raises(ValidationError):
        Settings()


def test_unknown_storage_backend_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_STORAGE__BACKEND", "s3")  # Phase 4
    with pytest.raises(ValidationError):
        Settings()


def test_upload_cap_derives_from_largest_tier() -> None:
    s = Settings()
    expected = 250 * 1024 * 1024 * 20 + s.limits.upload_overhead_bytes
    assert s.limits.max_upload_request_bytes == expected
    assert s.limits.max_job_timeout_seconds == 300

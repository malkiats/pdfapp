from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pdfapp.backend.app.core.config import (
    LimitsSettings,
    RateLimitSettings,
    Settings,
)
from pdfapp.backend.app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO_ROOT / "shared" / "openapi.yaml"
CATALOG_PATH = REPO_ROOT / "shared" / "tool-catalog.json"
CATALOG_SCHEMA_PATH = REPO_ROOT / "shared" / "tool-catalog.schema.json"


@pytest.fixture(autouse=True)
def _clean_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never inherit APP_* settings from the developer's shell."""
    for name in list(os.environ):
        if name.startswith("APP_"):
            monkeypatch.delenv(name, raising=False)


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "limits": LimitsSettings(),
        "rate_limit": RateLimitSettings(enabled=False),
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

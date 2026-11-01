from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from redis.asyncio import Redis

from pdfapp.backend.app.main import create_app
from pdfapp.backend.app.schemas.generated.models import Readiness
from pdfapp.backend.app.storage import InMemoryWorkspaceIndex, StorageUnavailable, TempFileManager
from pdfapp.backend.app.storage.backends.local import LocalBackend
from pdfapp.backend.tests.conftest import make_settings


async def _get(app: object, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        return await c.get(path)


async def test_health_is_dependency_free(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


async def test_ready_ok_with_redis_and_storage(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"redis": "ok", "storage": "ok"}}
    Readiness.model_validate(response.json())
    assert response.headers["cache-control"] == "no-store"


async def test_ready_without_redis_reports_not_configured(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    response = await _get(app, "/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"redis": "not_configured", "storage": "ok"}


async def test_ready_redis_down_is_clean_503(tmp_path: Path) -> None:
    unreachable = Redis.from_url(
        "redis://127.0.0.1:1/0", socket_connect_timeout=0.2, socket_timeout=0.2
    )
    app = create_app(make_settings(tmp_path), redis=unreachable)
    response = await _get(app, "/ready")
    assert response.status_code == 503
    body = response.json()
    assert body == {"status": "not_ready", "checks": {"redis": "failed", "storage": "ok"}}
    assert response.headers["content-type"] == "application/json"
    assert "127.0.0.1" not in response.text
    assert "Connection" not in response.text
    await unreachable.aclose()


async def test_ready_storage_failure_is_503(tmp_path: Path) -> None:
    class BrokenBackend(LocalBackend):
        async def ping(self) -> None:
            raise StorageUnavailable("storage not writable at /secret/path")

    settings = make_settings(tmp_path)
    manager = TempFileManager(
        BrokenBackend(tmp_path / "x"),
        InMemoryWorkspaceIndex(),
        retention=settings.retention,
        work_dir=tmp_path / "w",
        max_job_timeout_seconds=300,
    )
    app = create_app(settings, temp_files=manager)
    response = await _get(app, "/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["storage"] == "failed"
    assert "/secret/path" not in response.text


@pytest.mark.parametrize("path", ["/health", "/ready"])
async def test_probes_are_not_rate_limited(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path)
    assert "ratelimit-limit" not in response.headers

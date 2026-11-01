"""Security headers, CORS, request id, body-size guard, problem+json shape, catch-all."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request

from pdfapp.backend.app.core.logging import configure_logging
from pdfapp.backend.app.main import CORS_EXPOSE_HEADERS, create_app
from pdfapp.backend.app.middleware.rate_limit import InMemoryRateLimiter
from pdfapp.backend.app.schemas.generated.models import Problem
from pdfapp.backend.tests.conftest import make_settings

ORIGIN = "http://localhost:3000"
SECRET_MESSAGE = "CANARY /data/workspaces/secret-name.pdf"

EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-resource-policy": "same-site",
    "strict-transport-security": "max-age=63072000; includeSubDomains",
}


def _add_test_routes(app: FastAPI) -> None:
    @app.post("/api/v1/_test/echo-size")
    async def echo_size(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.get("/api/v1/_test/boom")
    async def boom() -> None:
        raise RuntimeError(SECRET_MESSAGE)


@pytest.fixture
async def test_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(tmp_path))
    _add_test_routes(app)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.parametrize(
    ("path", "status"),
    [("/health", 200), ("/api/v1/tools", 200), ("/api/v1/tools/zzz-unknown", 404), ("/nope", 404)],
)
async def test_security_headers_everywhere(
    client: httpx.AsyncClient, path: str, status: int
) -> None:
    response = await client.get(path)
    assert response.status_code == status
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers[name] == value
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "server" not in response.headers
    assert "x-powered-by" not in response.headers


async def test_errors_are_problem_json_and_no_store(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["cache-control"] == "no-store"
    Problem.model_validate(response.json())


async def test_method_not_allowed_is_problem(client: httpx.AsyncClient) -> None:
    response = await client.delete("/api/v1/tools")
    assert response.status_code == 405
    Problem.model_validate(response.json())


async def test_request_id_echo_and_replacement(client: httpx.AsyncClient) -> None:
    supplied = "client-req_12345678"
    response = await client.get("/health", headers={"X-Request-Id": supplied})
    assert response.headers["x-request-id"] == supplied
    for bad in ["short", "has spaces in it", "x" * 65, "<script>alert(1)</script>"]:
        replaced = await client.get("/health", headers={"X-Request-Id": bad})
        assert replaced.headers["x-request-id"] != bad
        assert replaced.headers["x-request-id"].startswith("req_")
    problem = await client.get("/nope", headers={"X-Request-Id": supplied})
    assert problem.json()["request_id"] == supplied


async def test_cors_preflight_allowed_origin(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/api/v1/tools",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Job-Token, If-None-Match, Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed = response.headers["access-control-allow-headers"].lower()
    for header in ("x-job-token", "if-none-match", "authorization", "content-type"):
        assert header in allowed


async def test_cors_simple_request_exposes_headers(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools", headers={"Origin": ORIGIN})
    assert response.headers["access-control-allow-origin"] == ORIGIN
    exposed = {
        h.strip().lower() for h in response.headers["access-control-expose-headers"].split(",")
    }
    assert {h.lower() for h in CORS_EXPOSE_HEADERS} <= exposed


async def test_cors_rejects_unlisted_origin(client: httpx.AsyncClient) -> None:
    evil = "https://evil.example.com"
    preflight = await client.options(
        "/api/v1/tools",
        headers={"Origin": evil, "Access-Control-Request-Method": "GET"},
    )
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers
    simple = await client.get("/api/v1/tools", headers={"Origin": evil})
    assert "access-control-allow-origin" not in simple.headers


async def test_body_size_guard_by_content_length(test_client: httpx.AsyncClient) -> None:
    ok = await test_client.post("/api/v1/_test/echo-size", content=b"x" * 1000)
    assert ok.json() == {"size": 1000}
    response = await test_client.post("/api/v1/_test/echo-size", content=b"x" * (1024 * 1024 + 1))
    assert response.status_code == 413
    problem = Problem.model_validate(response.json())
    assert problem.code.value == "file_too_large"
    assert problem.params is not None


async def test_body_size_guard_when_streamed(test_client: httpx.AsyncClient) -> None:
    async def body() -> AsyncIterator[bytes]:
        for _ in range(20):
            yield b"y" * (64 * 1024)

    response = await test_client.post("/api/v1/_test/echo-size", content=body())
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


async def test_bad_content_length_is_400(test_client: httpx.AsyncClient) -> None:
    response = await test_client.post(
        "/api/v1/_test/echo-size", content=b"x", headers={"Content-Length": "abc"}
    )
    assert response.status_code == 400


async def test_unhandled_exception_is_500_problem_without_details(
    test_client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO", json_output=True)  # bind the handler to capsys' stdout
    response = await test_client.get("/api/v1/_test/boom", headers={"Origin": ORIGIN})
    assert response.status_code == 500
    problem = Problem.model_validate(response.json())
    assert problem.code.value == "internal_error"
    assert "CANARY" not in response.text
    assert response.headers["x-request-id"] == problem.request_id
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["access-control-allow-origin"] == ORIGIN
    out = capsys.readouterr().out
    assert "CANARY" not in out
    assert "RuntimeError" in out


async def test_access_log_uses_route_template(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO", json_output=True)  # bind the handler to capsys' stdout
    await client.get("/api/v1/tools/merge-pdf?utm_source=CANARY-query")
    out = capsys.readouterr().out
    assert '"route": "/api/v1/tools/{slug}"' in out
    assert "CANARY-query" not in out
    assert "merge-pdf" not in out


async def test_rate_limit_returns_429_problem(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path), rate_limiter=InMemoryRateLimiter(2, 60))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        first = await c.get("/api/v1/tools")
        assert first.headers["ratelimit-remaining"] == "1"
        await c.get("/api/v1/tools")
        third = await c.get("/api/v1/tools", headers={"Origin": ORIGIN})
        assert (await c.get("/health")).status_code == 200  # probes are not limited
    assert third.status_code == 429
    problem = Problem.model_validate(third.json())
    assert problem.code.value == "rate_limited"
    assert problem.retry_after_seconds is not None
    assert third.headers["retry-after"] == str(problem.retry_after_seconds)
    assert third.headers["ratelimit-remaining"] == "0"
    assert third.headers["access-control-allow-origin"] == ORIGIN


async def test_openapi_hidden_in_prod(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path,
        env="prod",
        redis={"url": "redis://127.0.0.1:1/0"},
        security={"ip_hash_key": "p" * 40},
        cors={"allowed_origins": ["https://app.example.com"]},
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        assert (await c.get("/openapi.json")).status_code == 404
        assert (await c.get("/docs")).status_code == 404

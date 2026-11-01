from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pdfapp.backend.app.core.catalog import CatalogError
from pdfapp.backend.app.core.config import CatalogSettings, LimitsSettings
from pdfapp.backend.app.main import create_app
from pdfapp.backend.app.schemas.generated.models import Problem, Tool, ToolList
from pdfapp.backend.tests.conftest import CATALOG_PATH, CATALOG_SCHEMA_PATH, make_settings

CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


async def test_list_tools_serves_whole_catalog_in_order(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools")
    assert response.status_code == 200
    body = response.json()
    ToolList.model_validate(body)
    assert body["items"] == CATALOG["tools"]
    assert [t["slug"] for t in body["items"]] == [t["slug"] for t in CATALOG["tools"]]
    assert body["tier_limits"]["free"] == {
        "max_file_bytes": 26214400,
        "max_files_per_job": 5,
        "max_pages": 100,
        "job_timeout_seconds": 120,
    }
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.headers["etag"].startswith('"')
    assert response.headers["ratelimit-limit"] == "1000"


async def test_tier_limits_come_from_settings(tmp_path: Path) -> None:
    limits = LimitsSettings.model_validate({"free": {"max_files_per_job": 3}})
    app = create_app(make_settings(tmp_path, limits=limits))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        body = (await c.get("/api/v1/tools")).json()
    assert body["tier_limits"]["free"]["max_files_per_job"] == 3


@pytest.mark.parametrize(
    ("query", "predicate"),
    [
        ("category=ai", lambda t: t["category"] == "ai"),
        ("status=coming_soon", lambda t: t["status"] == "coming_soon"),
        ("status=available", lambda t: t["status"] == "available"),
        ("category=ocr&status=coming_soon", lambda t: t["category"] == "ocr"),
    ],
)
async def test_list_tools_filters(client: httpx.AsyncClient, query: str, predicate: object) -> None:
    response = await client.get(f"/api/v1/tools?{query}")
    assert response.status_code == 200
    expected = [t for t in CATALOG["tools"] if predicate(t)]  # type: ignore[operator]
    assert response.json()["items"] == expected


async def test_invalid_filter_is_validation_problem(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools?category=nope")
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    problem = Problem.model_validate(response.json())
    assert problem.code.value == "validation_error"
    assert problem.errors is not None
    assert problem.errors[0].pointer == "/category"
    assert "nope" not in response.text


async def test_etag_and_conditional_get(client: httpx.AsyncClient) -> None:
    first = await client.get("/api/v1/tools")
    etag = first.headers["etag"]
    for candidate in (etag, f"W/{etag}", f'"other", {etag}', "*"):
        again = await client.get("/api/v1/tools", headers={"If-None-Match": candidate})
        assert again.status_code == 304
        assert again.content == b""
        assert again.headers["etag"] == etag
    miss = await client.get("/api/v1/tools", headers={"If-None-Match": '"stale"'})
    assert miss.status_code == 200
    filtered = await client.get("/api/v1/tools?category=ai")
    assert filtered.headers["etag"] != etag


async def test_get_tool(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools/merge-pdf")
    assert response.status_code == 200
    tool = Tool.model_validate(response.json())
    assert tool.slug == "merge-pdf"
    assert response.json() == next(t for t in CATALOG["tools"] if t["slug"] == "merge-pdf")
    assert response.headers["etag"]


async def test_get_unknown_tool_is_404_problem(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = Problem.model_validate(response.json())
    assert problem.code.value == "tool_not_found"
    assert problem.type == "urn:problem:tool_not_found"
    assert problem.request_id == response.headers["x-request-id"]
    assert problem.instance == f"urn:request:{problem.request_id}"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("slug", ["UPPER", "ab", "bad--slug", "x" * 65])
async def test_get_tool_bad_slug_is_422(client: httpx.AsyncClient, slug: str) -> None:
    response = await client.get(f"/api/v1/tools/{slug}")
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_startup_fails_on_invalid_catalog(tmp_path: Path) -> None:
    bad = dict(CATALOG)
    bad["tools"] = [*CATALOG["tools"], CATALOG["tools"][0]]  # duplicate slug
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    catalog = CatalogSettings(path=path, schema_path=CATALOG_SCHEMA_PATH)
    with pytest.raises(CatalogError, match="duplicate slug"):
        create_app(make_settings(tmp_path, catalog=catalog))

    broken = dict(CATALOG["tools"][0])
    broken["category"] = "convert"
    path.write_text(json.dumps({"schema_version": 1, "tools": [broken]}), encoding="utf-8")
    with pytest.raises(CatalogError, match="invalid"):
        create_app(make_settings(tmp_path, catalog=catalog))

    missing = CatalogSettings(path=tmp_path / "nope.json", schema_path=CATALOG_SCHEMA_PATH)
    with pytest.raises(CatalogError, match="not found"):
        create_app(make_settings(tmp_path, catalog=missing))


def test_catalog_only_rule_file_tools_need_accepts(tmp_path: Path) -> None:
    entry = dict(next(t for t in CATALOG["tools"] if "file" in t["input_kinds"]))
    entry["accepts"] = []
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": 1, "tools": [entry]}), encoding="utf-8")
    with pytest.raises(CatalogError):
        create_app(
            make_settings(
                tmp_path, catalog=CatalogSettings(path=path, schema_path=CATALOG_SCHEMA_PATH)
            )
        )

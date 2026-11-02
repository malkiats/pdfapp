from __future__ import annotations

import json

import httpx
import pytest
from pdfapp.backend.tests.conftest import CATALOG_PATH

CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


async def test_list_tools_serves_whole_catalog_in_order(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == CATALOG["tools"]
    assert [t["slug"] for t in body["items"]] == [t["slug"] for t in CATALOG["tools"]]
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.headers["etag"].startswith('"')


async def test_list_tools_filters(client: httpx.AsyncClient) -> None:
    # Test category filter
    response = await client.get("/api/v1/tools?category=organize")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(t["category"] == "organize" for t in items)

    # Test status filter
    response = await client.get("/api/v1/tools?status=available")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(t["status"] == "available" for t in items)


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
    filtered = await client.get("/api/v1/tools?category=organize")
    assert filtered.headers["etag"] != etag


async def test_get_tool(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools/merge-pdf")
    assert response.status_code == 200
    assert response.json() == next(t for t in CATALOG["tools"] if t["slug"] == "merge-pdf")


@pytest.mark.parametrize("slug", ["does-not-exist", "UPPER"])
async def test_unknown_tool_is_404_problem(client: httpx.AsyncClient, slug: str) -> None:
    for response in (
        await client.get(f"/api/v1/tools/{slug}"),
        await client.post(f"/api/v1/{slug}", files={"files": ("a.pdf", b"%PDF-1.7")}),
    ):
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "not_found"
        assert response.json()["request_id"] == response.headers["x-request-id"]

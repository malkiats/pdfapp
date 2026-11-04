"""Large-file flow against a local moto S3 server (no real credentials, no network)."""

from __future__ import annotations

import io
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import boto3  # noqa: TID251 - test fixtures talk to moto directly
import httpx
import pikepdf
import pytest
from fastapi import FastAPI
from moto.server import ThreadedMotoServer
from pdfapp.backend.app.api import uploads
from pdfapp.backend.app.core.config import Settings
from pdfapp.backend.app.core.upload_ids import _b36, hour_bucket, new_upload_id
from pdfapp.backend.app.main import create_app
from pdfapp.backend.app.schemas.generated.models import CreateUploadResponse, UploadResult
from pdfapp.backend.tests.api.test_tool_endpoints import make_image, make_pdf
from pdfapp.backend.tests.conftest import make_settings

BUCKET = "test-bucket"
FAKE_KEY_ID = "test-access-key-id"  # moto accepts anything; never a real credential
FAKE_SECRET = "test-secret-access-key"
ORIGIN = {"Origin": "https://pdfapp-frontend.vercel.app"}


# ------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module")
def moto_endpoint() -> Iterator[str]:
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture
def s3(moto_endpoint: str) -> Any:
    httpx.post(f"{moto_endpoint}/moto-api/reset")
    client = boto3.client(
        "s3",
        endpoint_url=moto_endpoint,
        aws_access_key_id=FAKE_KEY_ID,
        aws_secret_access_key=FAKE_SECRET,
        region_name="us-east-1",
    )
    client.create_bucket(Bucket=BUCKET)
    return client


def r2_settings(tmp_path: Path, endpoint: str, **limits: int) -> Settings:
    base = make_settings(tmp_path)
    return make_settings(
        tmp_path,
        limits=base.limits.model_copy(update=limits),
        r2_access_key_id=FAKE_KEY_ID,
        r2_secret_access_key=FAKE_SECRET,
        r2_bucket_name=BUCKET,
        r2_endpoint=endpoint,
    )


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def r2_client(
    tmp_path: Path, moto_endpoint: str, s3: Any
) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(r2_settings(tmp_path, moto_endpoint))):
        yield c


def keys(s3: Any, prefix: str = "") -> list[str]:
    return [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", [])]


def pages_of(data: bytes) -> int:
    return len(pikepdf.open(io.BytesIO(data)).pages)


async def create(
    client: httpx.AsyncClient, tool: str, files: list[tuple[int, str]]
) -> httpx.Response:
    return await client.post(
        "/api/v1/uploads",
        json={"tool": tool, "files": [{"size": s, "content_type": t} for s, t in files]},
        headers=ORIGIN,
    )


async def create_and_put(
    client: httpx.AsyncClient, tool: str, blobs: list[bytes], *, put: list[int] | None = None
) -> dict[str, Any]:
    response = await create(client, tool, [(len(b), "application/pdf") for b in blobs])
    assert response.status_code == 201, response.text
    body = response.json()
    CreateUploadResponse.model_validate(body)
    for target in body["files"]:
        if put is not None and target["index"] not in put:
            continue
        async with httpx.AsyncClient() as storage:
            r = await storage.put(
                target["put_url"], content=blobs[target["index"]], headers=target["headers"]
            )
        assert r.status_code == 200, r.text
    return body  # type: ignore[no-any-return]


async def run(
    client: httpx.AsyncClient, upload_id: str, slug: str, body: dict[str, Any] | None = None
) -> httpx.Response:
    return await client.post(
        f"/api/v1/uploads/{upload_id}/run/{slug}", json=body or {}, headers=ORIGIN
    )


def upload_root(s3: Any, upload_id: str) -> str:
    matches = {k.split(upload_id)[0] for k in keys(s3, "pdfapp/") if upload_id in k}
    assert len(matches) <= 1
    return (matches.pop() if matches else "pdfapp/none/") + upload_id + "/"


# ------------------------------------------------------------------ not configured
async def test_not_configured_reports_disabled_and_503(client: httpx.AsyncClient) -> None:
    limits = (await client.get("/api/v1/tools")).json()["limits"]
    assert limits["large_files_enabled"] is False
    assert limits["max_large_file_bytes"] == 100 * 1024 * 1024
    assert limits["max_large_total_bytes"] == 250 * 1024 * 1024
    assert limits["inline_max_bytes"] == 4_194_304

    created = await create(client, "remove-pages", [(10, "application/pdf")])
    assert created.status_code == 503
    assert created.json()["code"] == "large_files_unavailable"
    upload_id = new_upload_id(int(time.time()), 1).value
    ran = await run(client, upload_id, "remove-pages")
    assert ran.status_code == 503
    assert (await client.delete(f"/api/v1/uploads/{upload_id}")).status_code == 204


async def test_configured_reports_enabled(r2_client: httpx.AsyncClient) -> None:
    limits = (await r2_client.get("/api/v1/tools")).json()["limits"]
    assert limits["large_files_enabled"] is True


# ------------------------------------------------------------------ happy path
async def test_create_put_run_delete_remove_pages(r2_client: httpx.AsyncClient, s3: Any) -> None:
    pdf = make_pdf(6)
    created = await create_and_put(r2_client, "remove-pages", [pdf])
    upload_id = created["upload_id"]
    target = created["files"][0]
    assert target["headers"] == {"Content-Type": "application/pdf", "Content-Length": str(len(pdf))}
    signed = parse_qs(urlsplit(target["put_url"]).query)["X-Amz-SignedHeaders"][0].split(";")
    assert {"content-length", "content-type", "host"} <= set(signed)

    stored = keys(s3, "pdfapp/")
    hour = hour_bucket(int(time.time()))
    assert len(stored) == 1
    assert stored[0].startswith(f"pdfapp/{hour[:8]}")
    assert stored[0].endswith(f"/{upload_id}/in/000")

    ran = await run(r2_client, upload_id, "remove-pages", {"options": {"pages": "1, 3-4"}})
    assert ran.status_code == 200, ran.text
    assert ran.headers["cache-control"] == "no-store"
    result = ran.json()
    UploadResult.model_validate(result)
    assert result["filename"] == "remove-pages-result.pdf"
    assert result["media_type"] == "application/pdf"

    async with httpx.AsyncClient() as storage:
        download = await storage.get(result["download_url"])
    assert download.status_code == 200
    assert pages_of(download.content) == 3
    assert result["size"] == len(download.content)
    assert "attachment" in download.headers.get("content-disposition", "")

    root = upload_root(s3, upload_id)
    assert keys(s3, root + "in/") == []  # inputs deleted right after the run
    assert keys(s3, root + "out/") == [root + "out/result.pdf"]

    deleted = await r2_client.delete(f"/api/v1/uploads/{upload_id}", headers=ORIGIN)
    assert deleted.status_code == 204
    assert keys(s3, root) == []
    # Idempotent.
    again = await r2_client.delete(f"/api/v1/uploads/{upload_id}")
    assert again.status_code == 204


async def test_merge_two_files_in_order(r2_client: httpx.AsyncClient, s3: Any) -> None:
    created = await create_and_put(r2_client, "merge-pdf", [make_pdf(2), make_pdf(3)])
    ran = await run(r2_client, created["upload_id"], "merge-pdf")
    assert ran.status_code == 200, ran.text
    async with httpx.AsyncClient() as storage:
        merged = await storage.get(ran.json()["download_url"])
    assert pages_of(merged.content) == 5


# ------------------------------------------------------------------ inputs deleted on failure
@pytest.mark.parametrize(
    ("options", "status", "code"),
    [
        ({"pages": "99"}, 400, "validation_error"),
        ({"pages": "1-3"}, 400, "validation_error"),  # removing every page
        ({"pages": ""}, 400, "validation_error"),
    ],
)
async def test_inputs_deleted_when_run_fails(
    r2_client: httpx.AsyncClient, s3: Any, options: dict[str, str], status: int, code: str
) -> None:
    created = await create_and_put(r2_client, "remove-pages", [make_pdf(3)])
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": options})
    assert ran.status_code == status, ran.text
    assert ran.json()["code"] == code
    assert ran.json()["errors"][0]["pointer"] == "/options/pages"
    assert keys(s3, "pdfapp/") == []


async def test_remove_every_page_message(r2_client: httpx.AsyncClient) -> None:
    created = await create_and_put(r2_client, "remove-pages", [make_pdf(3)])
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1-3"}})
    assert ran.json()["detail"] == "You cannot remove every page."


async def test_sniffed_type_rejected_and_inputs_deleted(
    r2_client: httpx.AsyncClient, s3: Any
) -> None:
    fake = make_image("PNG")  # declared application/pdf, really a PNG
    created = await create_and_put(r2_client, "remove-pages", [fake])
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert ran.status_code == 415
    assert ran.json()["code"] == "unsupported_type"
    assert keys(s3, "pdfapp/") == []


async def test_corrupt_pdf_is_422_and_inputs_deleted(r2_client: httpx.AsyncClient, s3: Any) -> None:
    created = await create_and_put(r2_client, "remove-pages", [b"%PDF-1.7 broken" * 10])
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert ran.status_code == 422
    assert ran.json()["code"] == "invalid_file"
    assert keys(s3, "pdfapp/") == []


async def test_large_page_cap_applies(tmp_path: Path, moto_endpoint: str, s3: Any) -> None:
    app = create_app(r2_settings(tmp_path, moto_endpoint, max_pages=2, max_large_pages=3))
    async for client in _client(app):
        ok = await create_and_put(client, "remove-pages", [make_pdf(3)])
        first = await run(client, ok["upload_id"], "remove-pages", {"options": {"pages": "1"}})
        assert first.status_code == 200
        big = await create_and_put(client, "remove-pages", [make_pdf(4)])
        ran = await run(client, big["upload_id"], "remove-pages", {"options": {"pages": "1"}})
        assert ran.status_code == 422
        assert ran.json()["code"] == "too_many_pages"


# ------------------------------------------------------------------ incomplete uploads
async def test_missing_put_is_409_and_keeps_other_inputs(
    r2_client: httpx.AsyncClient, s3: Any
) -> None:
    created = await create_and_put(r2_client, "merge-pdf", [make_pdf(1), make_pdf(1)], put=[0])
    ran = await run(r2_client, created["upload_id"], "merge-pdf")
    assert ran.status_code == 409
    body = ran.json()
    assert body["code"] == "upload_incomplete"
    assert [e["pointer"] for e in body["errors"]] == ["/files/1"]
    # Nothing processed yet: the client may PUT the missing file and retry.
    assert len(keys(s3, "pdfapp/")) == 1


async def test_ai_consent_required(r2_client: httpx.AsyncClient, s3: Any) -> None:
    created = await create_and_put(r2_client, "summarize-pdf", [make_pdf(1)])
    ran = await run(r2_client, created["upload_id"], "summarize-pdf", {"ai_consent": False})
    assert ran.status_code == 400
    assert ran.json()["errors"][0]["pointer"] == "/ai_consent"
    assert keys(s3, "pdfapp/") == []


# ------------------------------------------------------------------ createUpload rejections
@pytest.mark.parametrize(
    ("tool", "files", "status", "code"),
    [
        ("remove-pages", [(101 * 1024 * 1024, "application/pdf")], 413, "file_too_large"),
        ("merge-pdf", [(90 * 1024 * 1024, "application/pdf")] * 3, 413, "file_too_large"),
        ("remove-pages", [(10, "application/pdf")] * 2, 400, "too_many_files"),
        ("merge-pdf", [(10, "application/pdf")], 400, "validation_error"),
        ("remove-pages", [(10, "image/png")], 400, "unsupported_type"),
        ("no-such-tool", [(10, "application/pdf")], 404, "not_found"),
        ("compare-webpages", [(10, "application/pdf")], 400, "validation_error"),
        ("remove-pages", [(0, "application/pdf")], 400, "validation_error"),
        ("remove-pages", [(10, "text/html")], 400, "validation_error"),
        ("Bad_Slug", [(10, "application/pdf")], 400, "validation_error"),
    ],
)
async def test_create_rejections(
    r2_client: httpx.AsyncClient,
    s3: Any,
    tool: str,
    files: list[tuple[int, str]],
    status: int,
    code: str,
) -> None:
    response = await create(r2_client, tool, files)
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == code
    assert keys(s3) == []


async def test_create_rejects_unknown_fields_and_too_many_files(
    r2_client: httpx.AsyncClient,
) -> None:
    extra = await r2_client.post(
        "/api/v1/uploads",
        json={"tool": "remove-pages", "files": [{"size": 1, "content_type": "application/pdf",
                                                  "name": "secret.pdf"}]},
    )  # fmt: skip
    assert extra.status_code == 400
    assert extra.json()["code"] == "validation_error"
    many = await create(r2_client, "merge-pdf", [(10, "application/pdf")] * 21)
    assert many.status_code == 400
    malformed = await r2_client.post(
        "/api/v1/uploads", content=b"{nope", headers={"Content-Type": "application/json"}
    )
    assert malformed.status_code == 400


async def test_create_total_limit_is_configurable(
    tmp_path: Path, moto_endpoint: str, s3: Any
) -> None:
    app = create_app(r2_settings(tmp_path, moto_endpoint, max_large_total_bytes=100))
    async for client in _client(app):
        response = await create(client, "merge-pdf", [(60, "application/pdf")] * 2)
        assert response.status_code == 413
        assert response.json()["params"] == {"limit_bytes": 100}


# ------------------------------------------------------------------ upload ids
@pytest.mark.parametrize("bad_id", ["short", "a" * 129, "has.dot" + "a" * 40])
async def test_malformed_upload_id_is_400(r2_client: httpx.AsyncClient, bad_id: str) -> None:
    assert (await run(r2_client, bad_id, "remove-pages")).status_code == 400
    assert (await r2_client.delete(f"/api/v1/uploads/{bad_id}")).status_code == 400


async def test_unknown_or_expired_upload_id_is_404(r2_client: httpx.AsyncClient, s3: Any) -> None:
    now = int(time.time())
    token = "A" * 43
    candidates = [
        "A" * 40,  # contract-valid, not ours
        _b36(now - 2 * 3600, 7) + "1" + token,  # expired
        _b36(now + 3600, 7) + "1" + token,  # from the future
    ]
    for upload_id in candidates:
        response = await run(r2_client, upload_id, "remove-pages")
        assert response.status_code == 404, upload_id
        assert response.json()["code"] == "not_found"
        assert (await r2_client.delete(f"/api/v1/uploads/{upload_id}")).status_code == 204


async def test_unknown_tool_on_run_is_404(r2_client: httpx.AsyncClient) -> None:
    upload_id = new_upload_id(int(time.time()), 1).value
    assert (await run(r2_client, upload_id, "no-such-tool")).status_code == 404


async def test_never_uploaded_is_409(r2_client: httpx.AsyncClient) -> None:
    upload_id = new_upload_id(int(time.time()), 1).value
    response = await run(r2_client, upload_id, "remove-pages", {"options": {"pages": "1"}})
    assert response.status_code == 409


def test_upload_id_format() -> None:
    now = int(time.time())
    upload = new_upload_id(now, 20)
    assert len(upload.value) == 51
    from pdfapp.backend.app.core.upload_ids import UPLOAD_ID_RE, parse_upload_id

    assert UPLOAD_ID_RE.fullmatch(upload.value)
    parsed = parse_upload_id(upload.value, now)
    assert parsed is not None
    assert (parsed.created, parsed.count) == (now, 20)
    assert new_upload_id(now, 1).value != new_upload_id(now, 1).value
    with pytest.raises(ValueError, match="count"):
        new_upload_id(now, 21)


# ------------------------------------------------------------------ CORS
async def test_cors_allows_delete(r2_client: httpx.AsyncClient) -> None:
    upload_id = new_upload_id(int(time.time()), 1).value
    response = await r2_client.options(
        f"/api/v1/uploads/{upload_id}",
        headers={**ORIGIN, "Access-Control-Request-Method": "DELETE"},
    )
    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]


# ------------------------------------------------------------------ sweep via createUpload
async def test_create_upload_sweeps_stale_prefixes(
    r2_client: httpx.AsyncClient, s3: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(uploads, "SWEEP_ONE_IN", 1)
    now = int(time.time())
    stale = f"pdfapp/{hour_bucket(now - 3 * 3600)}/old/in/000"
    recent = f"pdfapp/{hour_bucket(now)}/new/in/000"
    for key in (stale, recent):
        s3.put_object(Bucket=BUCKET, Key=key, Body=b"x")
    assert (await create(r2_client, "remove-pages", [(10, "application/pdf")])).status_code == 201
    assert set(keys(s3)) == {recent}


# ------------------------------------------------------------------ inline path unchanged
async def test_inline_remove_pages_accepts_spaces(client: httpx.AsyncClient) -> None:
    from pdfapp.backend.tests.api.test_tool_endpoints import post

    response = await post(client, "remove-pages", [make_pdf(5)], {"pages": "1, 3-4"})
    assert response.status_code == 200, response.text
    assert pages_of(response.content) == 2
    everything = await post(client, "remove-pages", [make_pdf(2)], {"pages": "1-2"})
    assert everything.status_code == 400
    assert everything.json()["detail"] == "You cannot remove every page."


# ------------------------------------------------------------------ fix round: deletion guarantees
async def test_output_deleted_when_presign_get_fails(
    r2_client: httpx.AsyncClient, s3: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdfapp.backend.app.storage import r2

    def boom(*_: object, **__: object) -> str:
        raise r2.R2Unavailable("Boom")

    created = await create_and_put(r2_client, "remove-pages", [make_pdf(3)])
    monkeypatch.setattr(r2.R2Store, "presign_get", boom)
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert ran.status_code == 503
    assert ran.json()["code"] == "large_files_unavailable"
    assert keys(s3, "pdfapp/") == []


async def test_output_deleted_when_put_fails(
    r2_client: httpx.AsyncClient, s3: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdfapp.backend.app.storage import r2

    real_put = r2.R2Store.put_bytes

    def put_then_fail(self: r2.R2Store, key: str, data: bytes, content_type: str) -> None:
        real_put(self, key, data, content_type)  # the object lands, then the call "fails"
        raise r2.R2Unavailable("Timeout")

    created = await create_and_put(r2_client, "remove-pages", [make_pdf(3)])
    monkeypatch.setattr(r2.R2Store, "put_bytes", put_then_fail)
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert ran.status_code == 503
    assert keys(s3, "pdfapp/") == []


async def test_oversized_object_is_terminal_and_deleted(
    tmp_path: Path, moto_endpoint: str, s3: Any
) -> None:
    app = create_app(r2_settings(tmp_path, moto_endpoint, max_large_file_bytes=5000))
    async for client in _client(app):
        created = await create(client, "remove-pages", [(100, "application/pdf")])
        upload_id = created.json()["upload_id"]
        # Bypass the signed Content-Length (as a broken or hostile store might).
        put_url = created.json()["files"][0]["put_url"]
        object_key = urlsplit(put_url).path.split(f"/{BUCKET}/", 1)[1]
        s3.put_object(Bucket=BUCKET, Key=object_key, Body=b"%PDF" + b"0" * 6000)
        ran = await run(client, upload_id, "remove-pages", {"options": {"pages": "1"}})
        assert ran.status_code == 409
        assert keys(s3, "pdfapp/") == []


@pytest.mark.parametrize(
    ("slug", "status"),
    [
        ("no-such-tool", 404),
        ("merge-pdf", 400),  # 1 file uploaded, merge needs 2
        ("compare-webpages", 400),  # not a file tool
    ],
)
async def test_terminal_prechecks_delete_inputs(
    r2_client: httpx.AsyncClient, s3: Any, slug: str, status: int
) -> None:
    created = await create_and_put(r2_client, "remove-pages", [make_pdf(2)])
    ran = await run(r2_client, created["upload_id"], slug)
    assert ran.status_code == status, ran.text
    assert keys(s3, "pdfapp/") == []


async def test_second_run_is_refused(r2_client: httpx.AsyncClient, s3: Any) -> None:
    created = await create_and_put(r2_client, "remove-pages", [make_pdf(3)])
    first = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert first.status_code == 200
    root = upload_root(s3, created["upload_id"])
    assert root + "run.lock" in keys(s3, root)
    # Re-PUT the input with the still-valid URL: the lock still refuses a second run.
    async with httpx.AsyncClient() as storage:
        target = created["files"][0]
        await storage.put(target["put_url"], content=make_pdf(3), headers=target["headers"])
    second = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert second.status_code == 409
    assert second.json()["detail"] == "This upload has already been processed."
    assert (await r2_client.delete(f"/api/v1/uploads/{created['upload_id']}")).status_code == 204
    assert keys(s3, root) == []  # the lock and the re-PUT input are gone too


async def test_deadline_is_504_and_deletes_everything(
    r2_client: httpx.AsyncClient, s3: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = await create_and_put(r2_client, "remove-pages", [make_pdf(3)])
    monkeypatch.setattr(uploads, "RUN_DEADLINE_SECONDS", -1.0)
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert ran.status_code == 504
    assert ran.json()["code"] == "processing_timeout"
    assert keys(s3, "pdfapp/") == []


async def test_inputs_deleted_before_processing(
    r2_client: httpx.AsyncClient, s3: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []
    real = uploads.execute

    def spy(*args: Any) -> Any:
        seen.append(keys(s3, "pdfapp/"))
        return real(*args)

    monkeypatch.setattr(uploads, "execute", spy)
    created = await create_and_put(r2_client, "remove-pages", [make_pdf(3)])
    ran = await run(r2_client, created["upload_id"], "remove-pages", {"options": {"pages": "1"}})
    assert ran.status_code == 200
    assert len(seen) == 1
    assert not [k for k in seen[0] if "/in/" in k]


async def test_upload_rate_limits(tmp_path: Path, moto_endpoint: str, s3: Any) -> None:
    from pdfapp.backend.app.core.config import RateLimitSettings

    settings = r2_settings(tmp_path, moto_endpoint).model_copy(
        update={"rate_limit": RateLimitSettings(enabled=True, uploads_per_ip_per_minute=2)}
    )
    async for client in _client(create_app(settings)):
        codes = [
            (await create(client, "remove-pages", [(10, "application/pdf")])).status_code
            for _ in range(3)
        ]
        assert codes == [201, 201, 429]
        upload_id = new_upload_id(int(time.time()), 1).value
        runs = [(await run(client, upload_id, "remove-pages")).status_code for _ in range(3)]
        assert runs[-1] == 429
        limited = await run(client, upload_id, "remove-pages")
        assert limited.json()["code"] == "rate_limited"
        assert limited.headers["retry-after"]


# ------------------------------------------------------------------ fix round: render caps
async def test_pdf_to_images_rejects_huge_pages(client: httpx.AsyncClient) -> None:
    from pdfapp.backend.tests.api.test_tool_endpoints import post

    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(5000, 5000))  # 25 Mpt^2, ~58 Mpx at 110 dpi
    out = io.BytesIO()
    pdf.save(out)
    response = await post(client, "pdf-to-png", [out.getvalue()], {"dpi": "110"})
    assert response.status_code == 422
    assert response.json()["code"] == "processing_failed"
    small = await post(client, "pdf-to-png", [out.getvalue()], {"dpi": "50"})
    assert small.status_code == 200  # ~12 Mpx


def test_pdf_to_images_stops_at_output_cap() -> None:
    from pdfapp.backend.app.core.errors import ApiError
    from pdfapp.backend.app.lib import pdf_ops
    from pdfapp.backend.app.lib.common import ToolInput

    inp = ToolInput(files=[make_pdf(5)], options={"dpi": "72"}, max_output_bytes=100)
    with pytest.raises(ApiError) as exc:
        pdf_ops.pdf_to_images(inp, "png", "pdf-to-png")
    assert exc.value.code == "result_too_large"


# ------------------------------------------------------------------ hardening round: ocr_pdf
def test_ocr_pdf_pixel_cap_and_single_open(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    from pdfapp.backend.app.core.errors import ApiError
    from pdfapp.backend.app.lib import pdf_ops
    from pdfapp.backend.app.lib.common import ToolInput

    fake_tesseract = types.ModuleType("pytesseract")
    fake_tesseract.image_to_string = lambda _image: ""  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pytesseract", fake_tesseract)
    monkeypatch.setattr(pdf_ops, "_ocr_available", lambda: True)
    opened: list[int] = []
    real_doc = pdf_ops.pdfium.PdfDocument

    def counting_doc(*args: Any, **kwargs: Any) -> Any:
        opened.append(1)
        return real_doc(*args, **kwargs)

    monkeypatch.setattr(pdf_ops.pdfium, "PdfDocument", counting_doc)

    result = pdf_ops.ocr_pdf(ToolInput(files=[make_pdf(3)]))
    assert pages_of(result.content) == 3
    assert len(opened) == 1

    huge = pikepdf.new()
    huge.add_blank_page(page_size=(5000, 5000))  # ~108 Mpx at 150 dpi
    out = io.BytesIO()
    huge.save(out)
    with pytest.raises(ApiError) as exc:
        pdf_ops.ocr_pdf(ToolInput(files=[out.getvalue()]))
    assert exc.value.code == "processing_failed"

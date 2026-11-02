"""End-to-end tests for POST /api/v1/{slug}: every available tool, plus the error paths."""

from __future__ import annotations

import io
import json
import zipfile

import httpx
import pikepdf
import pytest
from pdfapp.backend.app.api.tools import HANDLERS
from pdfapp.backend.tests.conftest import CATALOG_PATH
from PIL import Image

ORIGIN = {"Origin": "https://pdfapp-frontend.vercel.app"}


def make_pdf(pages: int = 3, text: str = "Hello page") -> bytes:
    pdf = pikepdf.new()
    for i in range(pages):
        page = pdf.add_blank_page(page_size=(595, 842))
        font = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica
            )
        )
        page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
        page.obj.Contents = pdf.make_stream(f"BT /F1 24 Tf 72 700 Td ({text} {i + 1}) Tj ET".encode())
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def make_image(fmt: str) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 30, 30)).save(out, fmt)
    return out.getvalue()


PDF = make_pdf(3)
PDF2 = make_pdf(4, "Changed page")


async def post(
    client: httpx.AsyncClient,
    slug: str,
    files: list[bytes],
    options: dict[str, object] | None = None,
    **fields: str,
) -> httpx.Response:
    return await client.post(
        f"/api/v1/{slug}",
        files=[("files", (f"f{i}", f)) for i, f in enumerate(files)] or None,
        data={"options": json.dumps(options or {}), **fields},
        headers=ORIGIN,
    )


def pages_of(content: bytes) -> int:
    return len(pikepdf.open(io.BytesIO(content)).pages)


def test_every_available_tool_has_a_handler() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    available = {t["slug"] for t in catalog["tools"] if t["status"] == "available"}
    assert available == set(HANDLERS)


@pytest.mark.parametrize(
    ("slug", "files", "options", "expected_pages"),
    [
        ("merge-pdf", [PDF, PDF2], {}, 7),
        ("remove-pages", [PDF], {"pages": "2"}, 2),
        ("extract-pages", [PDF], {"pages": "1,3"}, 2),
        ("organize-pdf", [PDF], {"page_order": "3,1,2,2"}, 4),
        ("scan-to-pdf", [make_image("JPEG"), make_image("PNG")], {"page_size": "a4"}, 2),
        ("jpg-to-pdf", [make_image("JPEG")], {}, 1),
        ("png-to-pdf", [make_image("PNG")], {}, 1),
        ("compress-pdf", [PDF], {"level": "high"}, 3),
        ("repair-pdf", [PDF], {}, 3),
        ("rotate-pdf", [PDF], {"angle": "90", "pages": "1-2"}, 3),
        ("add-page-numbers", [PDF], {"format": "page-n-of-total"}, 3),
        ("add-watermark", [PDF], {"text": "CONFIDENTIAL"}, 3),
        ("crop-pdf", [PDF], {"margin_mm": "15"}, 3),
    ],
)
async def test_pdf_tools(
    client: httpx.AsyncClient,
    slug: str,
    files: list[bytes],
    options: dict[str, object],
    expected_pages: int,
) -> None:
    response = await post(client, slug, files, options)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["access-control-allow-origin"] == "*"
    assert f"{slug}-result.pdf" in response.headers["content-disposition"]
    assert pages_of(response.content) == expected_pages


@pytest.mark.parametrize(
    ("slug", "options", "names"),
    [
        ("split-pdf", {"ranges": "1-2,3"}, ["part-001.pdf", "part-002.pdf"]),
        ("split-pdf", {"every_n": "2"}, ["part-001.pdf", "part-002.pdf"]),
        ("pdf-to-jpg", {"dpi": "72"}, ["page-001.jpg", "page-002.jpg", "page-003.jpg"]),
        ("pdf-to-png", {"pages": "2"}, ["page-002.png"]),
    ],
)
async def test_zip_tools(
    client: httpx.AsyncClient, slug: str, options: dict[str, object], names: list[str]
) -> None:
    response = await post(client, slug, [PDF], options)
    assert response.status_code == 200, response.text
    assert zipfile.ZipFile(io.BytesIO(response.content)).namelist() == names


async def test_protect_then_unlock(client: httpx.AsyncClient) -> None:
    protected = await post(client, "protect-pdf", [PDF], {"password": "s3cret"})
    assert protected.status_code == 200
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(io.BytesIO(protected.content))
    wrong = await post(client, "unlock-pdf", [protected.content], {"password": "nope"})
    assert wrong.status_code == 422
    assert wrong.json()["code"] == "wrong_password"
    unlocked = await post(client, "unlock-pdf", [protected.content], {"password": "s3cret"})
    assert unlocked.status_code == 200
    assert pages_of(unlocked.content) == 3


async def test_compare_pdf_reports_differences(client: httpx.AsyncClient) -> None:
    response = await post(client, "compare-pdf", [PDF, PDF2])
    assert response.status_code == 200
    assert "Lines added:" in response.text
    assert "+Changed page 4" in response.text


@pytest.mark.parametrize(
    ("slug", "files", "options", "fields", "status", "code"),
    [
        ("merge-pdf", [PDF], {}, {}, 400, "validation_error"),
        ("split-pdf", [PDF], {"ranges": "9"}, {}, 400, "validation_error"),
        ("rotate-pdf", [PDF], {"angle": "45"}, {}, 400, "validation_error"),
        ("rotate-pdf", [make_image("PNG")], {}, {}, 400, "unsupported_type"),
        ("merge-pdf", [b"%PDF-broken", PDF], {}, {}, 422, "invalid_file"),
        ("word-to-pdf", [PDF], {}, {}, 404, "not_found"),
        ("summarize-pdf", [PDF], {}, {}, 400, "validation_error"),  # no consent
        ("summarize-pdf", [PDF], {}, {"ai_consent": "true"}, 503, "ai_unavailable"),  # no key
        (
            "compare-webpages",
            [],
            {},
            {"url_a": "http://127.0.0.1/", "url_b": "http://169.254.169.254/"},
            400,
            "url_blocked",
        ),
    ],
)
async def test_error_paths(
    client: httpx.AsyncClient,
    slug: str,
    files: list[bytes],
    options: dict[str, object],
    fields: dict[str, str],
    status: int,
    code: str,
) -> None:
    response = await post(client, slug, files, options, **fields)
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.json()["code"] == code


async def test_cors_preflight(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/api/v1/merge-pdf", headers={**ORIGIN, "Access-Control-Request-Method": "POST"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"

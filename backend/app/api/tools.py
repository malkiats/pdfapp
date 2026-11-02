"""Tool catalog and the synchronous tool endpoint: POST /api/v1/{slug}."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Annotated, Any, Final
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response
from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.lib import ai, pdf_ops, web
from pdfapp.backend.app.lib.common import ToolInput, ToolResult
from pdfapp.backend.app.lib.multipart import parse_multipart
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/v1", tags=["tools"])
log = get_logger(__name__)

CATALOG_CACHE_CONTROL: Final = "public, max-age=300"
TOOL_CACHE_CONTROL: Final = "no-store"
# Vercel Functions cannot return bodies above 4.5 MB.
MAX_RESULT_BYTES: Final = 4_400_000

Handler = Callable[[ToolInput], ToolResult]

HANDLERS: Final[dict[str, Handler]] = {
    # organize
    "merge-pdf": pdf_ops.merge_pdf,
    "split-pdf": pdf_ops.split_pdf,
    "remove-pages": pdf_ops.remove_pages,
    "extract-pages": pdf_ops.extract_pages,
    "organize-pdf": pdf_ops.organize_pdf,
    "scan-to-pdf": lambda i: pdf_ops.images_to_pdf(i, "scan-to-pdf"),
    # optimize
    "compress-pdf": pdf_ops.compress_pdf,
    "repair-pdf": pdf_ops.repair_pdf,
    # convert
    "jpg-to-pdf": lambda i: pdf_ops.images_to_pdf(i, "jpg-to-pdf"),
    "png-to-pdf": lambda i: pdf_ops.images_to_pdf(i, "png-to-pdf"),
    "pdf-to-jpg": lambda i: pdf_ops.pdf_to_images(i, "jpg", "pdf-to-jpg"),
    "pdf-to-png": lambda i: pdf_ops.pdf_to_images(i, "png", "pdf-to-png"),
    # edit
    "rotate-pdf": pdf_ops.rotate_pdf,
    "add-page-numbers": pdf_ops.add_page_numbers,
    "add-watermark": pdf_ops.add_watermark,
    "crop-pdf": pdf_ops.crop_pdf,
    # security
    "unlock-pdf": pdf_ops.unlock_pdf,
    "protect-pdf": pdf_ops.protect_pdf,
    "compare-pdf": pdf_ops.compare_pdf,
    # AI (only called with explicit consent)
    "summarize-pdf": ai.summarize_pdf,
    "summarize-article": ai.summarize_article,
    "translate-pdf": ai.translate_pdf,
    "translate-text": ai.translate_text,
    "pdf-to-markdown": ai.pdf_to_markdown,
    "extract-key-points": ai.extract_key_points,
    "ask-pdf": ai.ask_pdf,
    # compare
    "compare-webpages": web.compare_webpages,
}

_MAX_TEXT_CHARS: Final = 100_000


def _make_etag(data: bytes) -> str:
    return f'"{hashlib.md5(data).hexdigest()[:16]}"'  # noqa: S324 - cache key, not security


def _etag_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    if header.strip() == "*":
        return True
    candidates = {c.strip().removeprefix("W/") for c in header.split(",")}
    return etag in candidates


def _sniff_mime(data: bytes) -> str:
    """Decide the type from magic bytes; never trust the client's Content-Type."""
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    if b"\x00" not in data[:4096]:
        try:
            data[:65536].decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            pass
    return "application/octet-stream"


def _accepted(mime: str, accepts: list[str]) -> bool:
    normalized = {"image/jpg": "image/jpeg", "text/markdown": "text/plain"}
    allowed = {normalized.get(a, a) for a in accepts}
    return mime in allowed


def _find_tool(request: Request, slug: str) -> dict[str, Any]:
    for tool in request.app.state.catalog_data.get("tools", []):
        if tool.get("slug") == slug:
            return tool  # type: ignore[no-any-return]
    raise ApiError(404, "not_found", detail="No such tool.")


def _bad(code: str, message: str, pointer: str, status: int = 400) -> ApiError:
    return ApiError(
        status,
        code,
        detail=message,
        errors=[{"pointer": pointer, "code": code, "message": message}],
    )


@router.get("/tools", summary="List the tool catalog")
async def listTools(  # noqa: N802
    request: Request,
    category: Annotated[str | None, Query(max_length=40)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match", max_length=200)] = None,
) -> Response:
    """Returns the catalog plus global limits. Cacheable with ETag."""
    settings = request.app.state.settings
    items = request.app.state.catalog_data.get("tools", [])
    if category:
        items = [t for t in items if t.get("category") == category]
    if status:
        items = [t for t in items if t.get("status") == status]

    body = json.dumps(
        {
            "items": items,
            "limits": {
                "max_request_bytes": settings.limits.max_request_bytes,
                "max_pages": settings.limits.max_pages,
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    etag = _make_etag(body)
    headers = {"ETag": etag, "Cache-Control": CATALOG_CACHE_CONTROL}
    if _etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.get("/tools/{slug}", summary="Get one tool")
async def getTool(request: Request, slug: str) -> Response:  # noqa: N802
    body = json.dumps(_find_tool(request, slug), ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json",
        headers={"ETag": _make_etag(body), "Cache-Control": CATALOG_CACHE_CONTROL},
    )


@router.post("/{slug}", summary="Run a tool")
async def runTool(request: Request, slug: str) -> Response:  # noqa: N802
    tool = _find_tool(request, slug)
    handler = HANDLERS.get(slug)
    if tool.get("status") != "available" or handler is None:
        raise ApiError(404, "not_found", detail="This tool is not available yet.")

    content_type = request.headers.get("content-type", "")
    try:
        body = await request.body()
        if content_type.startswith("application/x-www-form-urlencoded"):
            form: dict[str, list[bytes] | str] = {
                k: v[-1] for k, v in parse_qs(body.decode("utf-8"), max_num_fields=20).items()
            }
        else:
            form = parse_multipart(body, content_type)
    except (ValueError, UnicodeDecodeError) as e:
        raise ApiError(400, "bad_request", detail="Send the request as multipart/form-data.") from e

    raw_files = form.get("files", [])
    files = raw_files if isinstance(raw_files, list) else []
    options_raw = form.get("options", "{}")
    try:
        options = json.loads(options_raw) if isinstance(options_raw, str) and options_raw else {}
    except json.JSONDecodeError as e:
        raise ApiError(400, "validation_error", detail="Options must be valid JSON.") from e
    if not isinstance(options, dict):
        raise ApiError(400, "validation_error", detail="Options must be a JSON object.")

    def text_field(name: str) -> str:
        value = form.get(name, "")
        return value if isinstance(value, str) else ""

    text = text_field("text")
    if len(text) > _MAX_TEXT_CHARS:
        raise _bad("validation_error", "The text is too long.", "/text")
    urls = [u for u in (text_field("url_a") or text_field("url"), text_field("url_b")) if u.strip()]

    kinds: list[str] = tool.get("input_kinds", [])
    if "file" in kinds and (files or kinds == ["file"]):
        lo, hi = int(tool.get("min_inputs", 1)), int(tool.get("max_inputs", 1))
        if len(files) < lo:
            raise _bad("validation_error", f"This tool needs at least {lo} file(s).", "/files")
        if len(files) > hi:
            raise _bad("too_many_files", f"This tool accepts at most {hi} file(s).", "/files")
        for i, data in enumerate(files):
            if not _accepted(_sniff_mime(data), tool.get("accepts", [])):
                raise _bad("unsupported_type", "File type not accepted.", f"/files/{i}")
    elif kinds == ["url"] and len(urls) < int(tool.get("min_inputs", 1)):
        raise _bad("validation_error", "Enter the page address(es).", "/url_a")
    elif not files and not urls and not text.strip():
        raise _bad("validation_error", "Provide some input.", "/text")

    if tool.get("requires_ai_consent") and text_field("ai_consent").lower() != "true":
        raise _bad("validation_error", "Consent is required for AI processing.", "/ai_consent")

    settings = request.app.state.settings
    tool_input = ToolInput(
        files=files,
        options=options,
        text=text,
        urls=urls,
        max_pages=settings.limits.max_pages,
        groq_api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
        groq_model=settings.groq_model,
    )
    try:
        result = await run_in_threadpool(handler, tool_input)
    except ApiError:
        raise
    except Exception as e:
        log.error("tool_failed", tool=slug, error_class=type(e).__name__)
        raise ApiError(422, "processing_failed", detail="The file could not be processed.") from e

    if len(result.content) > MAX_RESULT_BYTES:
        raise ApiError(
            413,
            "result_too_large",
            detail="The result is too large to download. Try fewer pages or lower quality.",
        )
    log.info("tool_succeeded", tool=slug, output_bytes=len(result.content))
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "Cache-Control": TOOL_CACHE_CONTROL,
        },
    )

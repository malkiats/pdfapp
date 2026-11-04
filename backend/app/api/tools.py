"""Tool catalog and the synchronous tool endpoint: POST /api/v1/{slug}."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Final
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response
from pdfapp.backend.app.api.tool_runner import (
    Handler,
    build_tool_input,
    check_options,
    execute,
    find_tool,
    runnable_tool,
    validate_inputs,
)
from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.lib import ai, pdf_ops, web
from pdfapp.backend.app.lib.common import result_too_large
from pdfapp.backend.app.lib.multipart import parse_multipart
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/v1", tags=["tools"])
log = get_logger(__name__)

CATALOG_CACHE_CONTROL: Final = "public, max-age=300"
TOOL_CACHE_CONTROL: Final = "no-store"
# Vercel Functions cannot return bodies above 4.5 MB.
MAX_RESULT_BYTES: Final = 4_400_000

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
    "ocr-pdf": pdf_ops.ocr_pdf,
    # convert
    "jpg-to-pdf": lambda i: pdf_ops.images_to_pdf(i, "jpg-to-pdf"),
    "png-to-pdf": lambda i: pdf_ops.images_to_pdf(i, "png-to-pdf"),
    "pdf-to-jpg": lambda i: pdf_ops.pdf_to_images(i, "jpg", "pdf-to-jpg"),
    "pdf-to-png": lambda i: pdf_ops.pdf_to_images(i, "png", "pdf-to-png"),
    # document conversions
    "word-to-pdf": pdf_ops.word_to_pdf,
    "powerpoint-to-pdf": pdf_ops.powerpoint_to_pdf,
    "excel-to-pdf": pdf_ops.excel_to_pdf,
    "html-to-pdf": pdf_ops.html_to_pdf,
    "pdf-to-word": pdf_ops.pdf_to_word,
    "pdf-to-powerpoint": pdf_ops.pdf_to_powerpoint,
    "pdf-to-excel": pdf_ops.pdf_to_excel,
    # edit
    "rotate-pdf": pdf_ops.rotate_pdf,
    "add-page-numbers": pdf_ops.add_page_numbers,
    "add-watermark": pdf_ops.add_watermark,
    "crop-pdf": pdf_ops.crop_pdf,
    "edit-pdf": pdf_ops.edit_pdf,
    "pdf-forms": pdf_ops.pdf_forms,
    "sign-pdf": pdf_ops.sign_pdf,
    "redact-pdf": pdf_ops.redact_pdf,
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
    # OCR-based image tools
    "image-to-text": pdf_ops.image_to_text,
    "jpg-to-text": pdf_ops.jpg_to_text,
    "png-to-text": pdf_ops.png_to_text,
    "screenshot-to-text": pdf_ops.screenshot_to_text,
    "scanned-document-to-text": pdf_ops.scanned_document_to_text,
    "receipt-to-text": pdf_ops.receipt_to_text,
    "handwriting-to-text": pdf_ops.handwriting_to_text,
}


def _make_etag(data: bytes) -> str:
    return f'"{hashlib.md5(data).hexdigest()[:16]}"'  # noqa: S324 - cache key, not security


def _etag_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    if header.strip() == "*":
        return True
    candidates = {c.strip().removeprefix("W/") for c in header.split(",")}
    return etag in candidates


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
                "large_files_enabled": settings.large_files_enabled,
                "max_large_file_bytes": settings.limits.max_large_file_bytes,
                "max_large_total_bytes": settings.limits.max_large_total_bytes,
                "inline_max_bytes": settings.limits.inline_max_bytes,
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
    body = json.dumps(find_tool(request, slug), ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json",
        headers={"ETag": _make_etag(body), "Cache-Control": CATALOG_CACHE_CONTROL},
    )


@router.post("/{slug}", summary="Run a tool")
async def runTool(request: Request, slug: str) -> Response:  # noqa: N802
    tool, handler = runnable_tool(request, slug, HANDLERS)

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
    options = check_options(options)

    def text_field(name: str) -> str:
        value = form.get(name, "")
        return value if isinstance(value, str) else ""

    text = text_field("text")
    urls = [u for u in (text_field("url_a") or text_field("url"), text_field("url_b")) if u.strip()]
    validate_inputs(
        tool,
        files=files,
        urls=urls,
        text=text,
        ai_consent=text_field("ai_consent").lower() == "true",
    )

    settings = request.app.state.settings
    tool_input = build_tool_input(
        settings,
        files=files,
        options=options,
        text=text,
        urls=urls,
        max_pages=settings.limits.max_pages,
        max_output_bytes=MAX_RESULT_BYTES,
    )
    result = await run_in_threadpool(execute, handler, tool_input, slug)

    if len(result.content) > MAX_RESULT_BYTES:
        raise result_too_large()
    log.info("tool_succeeded", tool=slug, output_bytes=len(result.content))
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "Cache-Control": TOOL_CACHE_CONTROL,
        },
    )

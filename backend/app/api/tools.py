"""Tool catalog and tool endpoints."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Final

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.core.scratch import cleanup_scratch_dir, create_scratch_dir
from pdfapp.backend.app.lib.compress_pdf import compress_pdf as compress_pdf_impl
from pdfapp.backend.app.lib.extract_text import extract_text as extract_text_impl
from pdfapp.backend.app.lib.image_to_pdf import image_to_pdf as image_to_pdf_impl
from pdfapp.backend.app.lib.merge_pdf import merge_pdf as merge_pdf_impl
from pdfapp.backend.app.lib.multipart import parse_multipart
from pdfapp.backend.app.lib.organize_pdf import organize_pdf as organize_pdf_impl
from pdfapp.backend.app.lib.pdf_to_images import pdf_to_images as pdf_to_images_impl
from pdfapp.backend.app.lib.rotate_pdf import rotate_pdf as rotate_pdf_impl
from pdfapp.backend.app.lib.split_pdf import split_pdf as split_pdf_impl

router = APIRouter(prefix="/api/v1", tags=["tools"])
log = get_logger(__name__)

CATALOG_CACHE_CONTROL: Final = "public, max-age=300"
TOOL_CACHE_CONTROL: Final = "no-store"

# Allowed MIME types per tool
ALLOWED_MIMES = {
    "merge-pdf": {"application/pdf"},
    "split-pdf": {"application/pdf"},
    "organize-pdf": {"application/pdf"},
    "rotate-pdf": {"application/pdf"},
    "compress-pdf": {"application/pdf"},
    "image-to-pdf": {"image/png", "image/jpeg", "image/jpg", "image/webp"},
    "pdf-to-images": {"application/pdf"},
    "extract-text": {"application/pdf"},
}


def _make_etag(data: bytes) -> str:
    """Create an ETag from data."""
    return f'"{hashlib.md5(data).hexdigest()[:8]}"'  # noqa: S324


def _sniff_mime(data: bytes) -> str:
    """Guess MIME type from magic bytes."""
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG"):
        return "image/png"
    return "application/octet-stream"


def _validate_files(files: list[bytes], expected_mimes: set[str]) -> None:
    """Validate that all files have the expected MIME types."""
    for i, file_bytes in enumerate(files):
        mime = _sniff_mime(file_bytes)
        if mime not in expected_mimes:
            raise ApiError(
                400,
                "unsupported_type",
                detail="One of the files is not a type this tool accepts.",
                errors=[
                    {
                        "pointer": f"/files/{i}",
                        "code": "unsupported_type",
                        "message": "File type not accepted.",
                    }
                ],
            )


@router.get(
    "/tools",
    summary="List the tool catalog",
    responses={
        200: {"description": "The catalog."},
        304: {"description": "Catalog unchanged."},
    },
)
async def listTools(  # noqa: N802
    request: Request,
    category: Annotated[
        str | None, Query(description="Return only tools in this category.")
    ] = None,
    status: Annotated[
        str | None, Query(description="Return only tools with this status.")
    ] = None,
    if_none_match: Annotated[
        str | None,
        Header(
            alias="If-None-Match",
            max_length=200,
            description="ETag from a previous response.",
        ),
    ] = None,
) -> Response:
    """Returns the catalog plus global limits. Cacheable with ETag."""
    catalog = request.app.state.catalog_data
    settings = request.app.state.settings

    # Filter by category and status if provided
    items = catalog.get("tools", [])
    if category:
        items = [t for t in items if t.get("category") == category]
    if status:
        items = [t for t in items if t.get("status") == status]

    # Build response
    body_dict = {
        "items": items,
        "limits": {
            "max_request_bytes": settings.limits.max_request_bytes,
            "max_pages": settings.limits.max_pages,
        },
    }
    body = json.dumps(body_dict, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    etag = _make_etag(body)

    # 304 if ETag matches
    if if_none_match and if_none_match.strip('"') == etag.strip('"'):
        return Response(
            status_code=304,
            headers={"ETag": etag, "Cache-Control": CATALOG_CACHE_CONTROL},
        )

    return Response(
        content=body,
        media_type="application/json",
        headers={
            "ETag": etag,
            "Cache-Control": CATALOG_CACHE_CONTROL,
            "RateLimit-Limit": "999",
            "RateLimit-Remaining": "999",
            "RateLimit-Reset": "60",
        },
    )


@router.post(
    "/merge-pdf",
    summary="Merge PDF files",
    responses={
        200: {"description": "Merged PDF"},
        400: {"description": "Bad request"},
        413: {"description": "Too large"},
        422: {"description": "Can't process"},
        504: {"description": "Timeout"},
    },
)
async def mergePdf(request: Request) -> Response:  # noqa: N802
    """Merge PDF files (2-20, in specified order)."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")

        # Parse multipart form data
        try:
            form_data = parse_multipart(body, content_type)
        except Exception as e:
            msg = "The request body could not be parsed."
            raise ApiError(400, "bad_request", detail=msg) from e

        # Extract files and options
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]

        options_str = form_data.get("options", "{}")
        try:
            options = (
                json.loads(options_str)  # type: ignore[arg-type]
                if isinstance(options_str, str)
                else options_str
            )
        except json.JSONDecodeError as e:
            msg = "Options must be valid JSON."
            raise ApiError(400, "validation_error", detail=msg) from e

        # Validate file types
        _validate_files(files, ALLOWED_MIMES["merge-pdf"])  # type: ignore[arg-type]

        # Call tool
        result = merge_pdf_impl(files, options, scratch_dir)  # type: ignore[arg-type]

        # Return as file
        return Response(
            content=result,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="merge-pdf-result.pdf"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )

    except ApiError:
        raise
    except Exception as e:
        log.error("merge_pdf_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


# Stubs for remaining Phase 2 tools (will be implemented similarly)

@router.post("/split-pdf", summary="Split PDF")
async def splitPdf(request: Request) -> Response:  # noqa: N802
    """Split PDF into pages."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        form_data = parse_multipart(body, content_type)
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]
        options_str = form_data.get("options", "{}")
        options = (
            json.loads(options_str)  # type: ignore[arg-type]
            if isinstance(options_str, str)
            else options_str
        )
        _validate_files(files, ALLOWED_MIMES["split-pdf"])  # type: ignore[arg-type]
        result = split_pdf_impl(files, options, scratch_dir)  # type: ignore[arg-type]
        return Response(
            content=result,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="split-pdf-result.zip"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )
    except ApiError:
        raise
    except Exception as e:
        log.error("split_pdf_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


@router.post("/organize-pdf", summary="Organize PDF pages")
async def organizePdf(request: Request) -> Response:  # noqa: N802
    """Organize PDF pages."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        form_data = parse_multipart(body, content_type)
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]
        options_str = form_data.get("options", "{}")
        options = (
            json.loads(options_str)  # type: ignore[arg-type]
            if isinstance(options_str, str)
            else options_str
        )
        _validate_files(files, ALLOWED_MIMES["organize-pdf"])  # type: ignore[arg-type]
        result = organize_pdf_impl(files, options, scratch_dir)  # type: ignore[arg-type]
        return Response(
            content=result,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="organize-pdf-result.pdf"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )
    except ApiError:
        raise
    except Exception as e:
        log.error("organize_pdf_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


@router.post("/rotate-pdf", summary="Rotate PDF pages")
async def rotatePdf(request: Request) -> Response:  # noqa: N802
    """Rotate PDF pages."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        form_data = parse_multipart(body, content_type)
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]
        options_str = form_data.get("options", "{}")
        options = (
            json.loads(options_str)  # type: ignore[arg-type]
            if isinstance(options_str, str)
            else options_str
        )
        _validate_files(files, ALLOWED_MIMES["rotate-pdf"])  # type: ignore[arg-type]
        result = rotate_pdf_impl(files, options, scratch_dir)  # type: ignore[arg-type]
        return Response(
            content=result,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="rotate-pdf-result.pdf"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )
    except ApiError:
        raise
    except Exception as e:
        log.error("rotate_pdf_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


@router.post("/compress-pdf", summary="Compress PDF")
async def compressPdf(request: Request) -> Response:  # noqa: N802
    """Compress PDF."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        form_data = parse_multipart(body, content_type)
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]
        options_str = form_data.get("options", "{}")
        options = (
            json.loads(options_str)  # type: ignore[arg-type]
            if isinstance(options_str, str)
            else options_str
        )
        _validate_files(files, ALLOWED_MIMES["compress-pdf"])  # type: ignore[arg-type]
        result = compress_pdf_impl(files, options, scratch_dir)  # type: ignore[arg-type]
        return Response(
            content=result,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="compress-pdf-result.pdf"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )
    except ApiError:
        raise
    except Exception as e:
        log.error("compress_pdf_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


@router.post("/image-to-pdf", summary="Convert images to PDF")
async def imageToPdf(request: Request) -> Response:  # noqa: N802
    """Convert images to PDF."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        form_data = parse_multipart(body, content_type)
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]
        options_str = form_data.get("options", "{}")
        options = (
            json.loads(options_str)  # type: ignore[arg-type]
            if isinstance(options_str, str)
            else options_str
        )
        _validate_files(files, ALLOWED_MIMES["image-to-pdf"])  # type: ignore[arg-type]
        result = image_to_pdf_impl(files, options, scratch_dir)  # type: ignore[arg-type]
        return Response(
            content=result,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="image-to-pdf-result.pdf"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )
    except ApiError:
        raise
    except Exception as e:
        log.error("image_to_pdf_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


@router.post("/pdf-to-images", summary="Convert PDF to images")
async def pdfToImages(request: Request) -> Response:  # noqa: N802
    """Convert PDF to images."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        form_data = parse_multipart(body, content_type)
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]
        options_str = form_data.get("options", "{}")
        options = (
            json.loads(options_str)  # type: ignore[arg-type]
            if isinstance(options_str, str)
            else options_str
        )
        _validate_files(files, ALLOWED_MIMES["pdf-to-images"])  # type: ignore[arg-type]
        result = pdf_to_images_impl(files, options, scratch_dir)  # type: ignore[arg-type]
        return Response(
            content=result,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="pdf-to-images-result.zip"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )
    except ApiError:
        raise
    except Exception as e:
        log.error("pdf_to_images_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


@router.post("/extract-text", summary="Extract text from PDF")
async def extractText(request: Request) -> Response:  # noqa: N802
    """Extract text from PDF."""
    scratch_dir = create_scratch_dir()
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        form_data = parse_multipart(body, content_type)
        files = form_data.get("files", [])
        if not isinstance(files, list):
            files = [files]  # type: ignore[list-item]
        options_str = form_data.get("options", "{}")
        options = (
            json.loads(options_str)  # type: ignore[arg-type]
            if isinstance(options_str, str)
            else options_str
        )
        _validate_files(files, ALLOWED_MIMES["extract-text"])  # type: ignore[arg-type]
        result = extract_text_impl(files, options, scratch_dir)  # type: ignore[arg-type]
        return Response(
            content=result,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="extract-text-result.txt"',
                "Cache-Control": TOOL_CACHE_CONTROL,
                "RateLimit-Limit": "999",
                "RateLimit-Remaining": "999",
                "RateLimit-Reset": "60",
            },
        )
    except ApiError:
        raise
    except Exception as e:
        log.error("extract_text_handler_error", error_class=type(e).__name__)
        raise ApiError(500, "internal_error", detail="Something went wrong.") from e
    finally:
        cleanup_scratch_dir(scratch_dir)


@router.post("/compare-sites", summary="Compare two web pages")
async def compareSites(request: Request) -> Response:  # noqa: N802
    """Compare two web pages. Phase 3 - coming soon."""
    raise ApiError(404, "not_found", detail="This endpoint is not yet implemented.")

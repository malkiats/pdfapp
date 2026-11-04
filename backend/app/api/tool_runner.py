"""Validation and execution shared by the inline route and the large-file route.

Both flows must apply exactly the same rules (input count, sniffed type, consent,
options shape) and call the same handler, so they live here once.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from fastapi import Request
from pdfapp.backend.app.core.config import Settings
from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.lib.common import ToolInput, ToolResult

log = get_logger(__name__)

Handler = Callable[[ToolInput], ToolResult]

MAX_TEXT_CHARS: Final = 100_000
_NORMALIZED_TYPES: Final = {"image/jpg": "image/jpeg", "text/markdown": "text/plain"}


def sniff_mime(data: bytes) -> str:
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


def accepted(mime: str, accepts: list[str]) -> bool:
    allowed = {_NORMALIZED_TYPES.get(a, a) for a in accepts}
    return _NORMALIZED_TYPES.get(mime, mime) in allowed


def bad(code: str, message: str, pointer: str, status: int = 400) -> ApiError:
    return ApiError(
        status,
        code,
        detail=message,
        errors=[{"pointer": pointer, "code": code, "message": message}],
    )


def find_tool(request: Request, slug: str) -> dict[str, Any]:
    for tool in request.app.state.catalog_data.get("tools", []):
        if tool.get("slug") == slug:
            return tool  # type: ignore[no-any-return]
    raise ApiError(404, "not_found", detail="No such tool.")


def runnable_tool(
    request: Request, slug: str, handlers: dict[str, Handler]
) -> tuple[dict[str, Any], Handler]:
    tool = find_tool(request, slug)
    handler = handlers.get(slug)
    if tool.get("status") != "available" or handler is None:
        raise ApiError(404, "not_found", detail="This tool is not available yet.")
    return tool, handler


def check_file_count(tool: dict[str, Any], count: int) -> None:
    lo, hi = int(tool.get("min_inputs", 1)), int(tool.get("max_inputs", 1))
    if count < lo:
        raise bad("validation_error", f"This tool needs at least {lo} file(s).", "/files")
    if count > hi:
        raise bad("too_many_files", f"This tool accepts at most {hi} file(s).", "/files")


def validate_inputs(
    tool: dict[str, Any],
    *,
    files: list[bytes],
    urls: list[str],
    text: str,
    ai_consent: bool,
    unsupported_status: int = 400,
) -> None:
    """The inline route's input rules, verbatim. Raises ApiError."""
    if len(text) > MAX_TEXT_CHARS:
        raise bad("validation_error", "The text is too long.", "/text")
    kinds: list[str] = tool.get("input_kinds", [])
    if "file" in kinds and (files or kinds == ["file"]):
        check_file_count(tool, len(files))
        for i, data in enumerate(files):
            if not accepted(sniff_mime(data), tool.get("accepts", [])):
                raise bad(
                    "unsupported_type", "File type not accepted.", f"/files/{i}",
                    unsupported_status,
                )  # fmt: skip
    elif kinds == ["url"] and len(urls) < int(tool.get("min_inputs", 1)):
        raise bad("validation_error", "Enter the page address(es).", "/url_a")
    elif not files and not urls and not text.strip():
        raise bad("validation_error", "Provide some input.", "/text")

    if tool.get("requires_ai_consent") and not ai_consent:
        raise bad("validation_error", "Consent is required for AI processing.", "/ai_consent")


def check_options(options: object) -> dict[str, Any]:
    if not isinstance(options, dict):
        raise ApiError(400, "validation_error", detail="Options must be a JSON object.")
    return options


def build_tool_input(
    settings: Settings,
    *,
    files: list[bytes],
    options: dict[str, Any],
    text: str,
    urls: list[str],
    max_pages: int,
    max_output_bytes: int,
) -> ToolInput:
    return ToolInput(
        files=files,
        options=options,
        text=text,
        urls=urls,
        max_pages=max_pages,
        max_output_bytes=max_output_bytes,
        groq_api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
        groq_model=settings.groq_model,
    )


def execute(handler: Handler, tool_input: ToolInput, slug: str) -> ToolResult:
    """Runs a handler (blocking). Unexpected failures become 422 processing_failed."""
    try:
        return handler(tool_input)
    except ApiError:
        raise
    except Exception as e:
        log.error("tool_failed", tool=slug, error_class=type(e).__name__)
        raise ApiError(422, "processing_failed", detail="The file could not be processed.") from e

"""Error handling: RFC 9457 problem+json responses."""

from __future__ import annotations

from typing import Final

from fastapi.responses import JSONResponse

from pdfapp.backend.app.core.request_context import current_request_id, new_request_id

PROBLEM_MEDIA_TYPE: Final = "application/problem+json"

TITLES: Final[dict[str, str]] = {
    "bad_request": "Malformed request",
    "validation_error": "Validation failed",
    "file_too_large": "File too large",
    "too_many_files": "Too many files",
    "too_many_pages": "Too many pages",
    "unsupported_type": "Unsupported file type",
    "type_mismatch": "File types do not match",
    "invalid_file": "Invalid file",
    "file_encrypted": "File is password protected",
    "rate_limited": "Too many requests",
    "processing_failed": "Processing failed",
    "processing_timeout": "Processing timed out",
    "upstream_fetch_failed": "Could not fetch the page",
    "url_blocked": "URL not allowed",
    "internal_error": "Internal error",
    "not_found": "Not found",
}


class ApiError(Exception):
    """Raise to render as problem+json."""

    def __init__(
        self,
        status: int,
        code: str,
        *,
        detail: str | None = None,
        params: dict[str, str | int | bool] | None = None,
        errors: list[dict[str, str]] | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.detail = detail
        self.params = params
        self.errors = errors
        self.retry_after_seconds = retry_after_seconds


def problem_response(
    code: str,
    status: int,
    *,
    detail: str | None = None,
    params: dict[str, str | int | bool] | None = None,
    errors: list[dict[str, str]] | None = None,
    retry_after_seconds: int | None = None,
    title: str | None = None,
) -> JSONResponse:
    """Render an error as RFC 9457 problem+json."""
    request_id = current_request_id() or new_request_id()

    body = {
        "type": f"urn:problem:{code}",
        "title": title or TITLES.get(code, code),
        "status": status,
        "code": code,
        "request_id": request_id,
        "instance": f"urn:request:{request_id}",
    }

    if detail:
        body["detail"] = detail
    if params:
        body["params"] = params
    if errors:
        body["errors"] = errors
    if retry_after_seconds:
        body["retry_after_seconds"] = retry_after_seconds

    headers = {"Cache-Control": "no-store"}
    if retry_after_seconds:
        headers["Retry-After"] = str(retry_after_seconds)

    return JSONResponse(
        content=body,
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )

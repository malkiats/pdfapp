"""Exception handlers for the FastAPI app."""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from pdfapp.backend.app.core.errors import ApiError, problem_response
from pdfapp.backend.app.core.logging import get_logger
from starlette.exceptions import HTTPException as StarletteHTTPException

log = get_logger(__name__)

_LOCATION_ROOTS: Final = frozenset({"body", "query", "path", "header", "cookie"})
_MAX_ERRORS: Final = 50


def _pointer(loc: list[str] | tuple[str, ...]) -> str:
    """Convert a Pydantic error location to a JSON Pointer."""
    parts = list(loc)
    if parts and parts[0] in _LOCATION_ROOTS:
        parts = parts[1:]
    escaped = [str(p).replace("~", "~0").replace("/", "~1") for p in parts]
    return ("/" + "/".join(escaped))[:200]


async def handle_api_error(request: Request, exc: ApiError) -> Response:
    """Handle ApiError exceptions."""
    log.warning(
        "api_error",
        status=exc.status,
        code=exc.code,
        error_class=type(exc).__name__,
    )
    return problem_response(
        exc.code,
        exc.status,
        detail=exc.detail,
        params=exc.params,
        errors=exc.errors,
        retry_after_seconds=exc.retry_after_seconds,
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
    """Handle Pydantic validation errors."""
    errors = exc.errors()

    if any(err.get("type") == "json_invalid" for err in errors):
        return problem_response(
            "bad_request",
            400,
            detail="The request body could not be parsed.",
        )

    field_errors = []
    for err in errors[:_MAX_ERRORS]:
        field_errors.append(
            {
                "pointer": _pointer(err.get("loc", ())),
                "code": str(err.get("type", "invalid"))[:64],
                "message": str(err.get("msg", "Invalid value."))[:300],
            }
        )

    # The contract maps validation_error to 400 (ErrorCode table), not FastAPI's 422.
    return problem_response(
        "validation_error",
        400,
        detail="One or more fields are invalid.",
        errors=field_errors,
    )


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
    """Handle Starlette HTTP exceptions."""
    status = exc.status_code

    if status == 404:
        return problem_response(
            "not_found",
            404,
            detail="No such endpoint.",
        )
    if status == 405:
        return problem_response(
            "bad_request",
            405,
            detail="Method not allowed.",
        )
    if status == 413:
        return problem_response(
            "file_too_large",
            413,
            detail="The upload exceeds the maximum size.",
        )
    if status == 429:
        return problem_response(
            "rate_limited",
            429,
            detail="Slow down and retry shortly.",
            retry_after_seconds=30,
        )

    return problem_response(
        "internal_error",
        500,
        detail="Something went wrong. Quote the request id if you contact support.",
    )


async def handle_generic_exception(request: Request, exc: Exception) -> Response:
    """Handle any unhandled exception."""
    log.error(
        "unhandled_exception",
        error_class=type(exc).__name__,
    )
    return problem_response(
        "internal_error",
        500,
        detail="Something went wrong. Quote the request id if you contact support.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_generic_exception)

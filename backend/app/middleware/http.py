"""ASGI middleware: request context, security headers, body size limit."""

from __future__ import annotations

import time
from typing import Final

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pdfapp.backend.app.core.errors import problem_response
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.core.request_context import (
    REQUEST_ID_HEADER,
    is_valid_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)

log = get_logger("app.access")

API_CSP: Final = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def _route_template(scope: Scope) -> str:
    """Extract the route template from scope."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "<unmatched>"


class RequestContextMiddleware:
    """Assigns X-Request-Id and logs each request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and is_valid_request_id(incoming) else new_request_id()
        token = set_request_id(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log.info(
                "http_request",
                method=scope.get("method"),
                route=_route_template(scope),
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            reset_request_id(token)


class SecurityHeadersMiddleware:
    """Adds security headers to all responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.static = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": API_CSP,
            "Cross-Origin-Resource-Policy": "same-site",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.static.items():
                    headers[name] = value
                if "cache-control" not in headers:
                    headers["Cache-Control"] = "no-store"
                for banner in ("server", "x-powered-by"):
                    if banner in headers:
                        del headers[banner]
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodySizeLimitMiddleware:
    """Enforces request body size limit."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check Content-Length header
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    response = problem_response(
                        "file_too_large",
                        413,
                        detail="The upload exceeds the maximum size.",
                        params={"limit_bytes": self.max_bytes},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = problem_response(
                    "bad_request",
                    400,
                    detail="The request body could not be parsed.",
                )
                await response(scope, receive, send)
                return

        # Stream and count bytes
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RuntimeError("file_too_large")
            return message

        await self.app(scope, limited_receive, send)

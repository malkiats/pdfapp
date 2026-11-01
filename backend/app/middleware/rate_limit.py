"""Simple in-memory rate limiting by client IP (Phase 1)."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pdfapp.backend.app.core.errors import problem_response
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)

API_PREFIX: Final = "/api/v1"
_MAX_MEMORY_KEYS: Final = 50_000


def client_ip(headers: dict[str, str]) -> str:
    """Extract client IP from headers. Simplified: just use remote addr."""
    return headers.get("client", "127.0.0.1")


def hash_client(ip: str) -> str:
    """Hash the IP address so we don't log it."""
    return hashlib.md5(ip.encode()).hexdigest()[:8]  # noqa: S324


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


class InMemoryRateLimiter:
    """Fixed-window rate limiter, per-IP, in memory."""

    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self.window = 60  # seconds
        self._counts: dict[tuple[str, int], int] = {}

    async def hit(self, key: str) -> RateLimitResult:
        """Check rate limit for a key (IP hash)."""
        now = time.time()
        window_index = int(now // self.window)

        # Clean old windows
        if len(self._counts) > _MAX_MEMORY_KEYS:
            self._counts = {k: v for k, v in self._counts.items() if k[1] >= window_index - 1}

        bucket = (key, window_index)
        count = self._counts.get(bucket, 0) + 1
        self._counts[bucket] = count

        reset = max(1, math.ceil((window_index + 1) * self.window - now))

        return RateLimitResult(
            allowed=count <= self.limit,
            limit=self.limit,
            remaining=max(0, self.limit - count),
            reset_seconds=reset,
        )


class RateLimitMiddleware:
    """Middleware to enforce rate limits."""

    def __init__(self, app: ASGIApp, *, rate_limiter: InMemoryRateLimiter) -> None:
        self.app = app
        self.limiter = rate_limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith(API_PREFIX):
            await self.app(scope, receive, send)
            return

        # Get client IP from ASGI scope
        client = scope.get("client") or ("127.0.0.1", 0)
        ip = client[0]
        key = hash_client(ip)

        # Check rate limit
        result = await self.limiter.hit(key)

        if not result.allowed:
            response = problem_response(
                "rate_limited",
                429,
                detail="Slow down and retry shortly.",
                retry_after_seconds=result.reset_seconds,
            )
            await response(scope, receive, send)
            return

        # Wrap send to add rate limit headers
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["RateLimit-Limit"] = str(result.limit)
                headers["RateLimit-Remaining"] = str(result.remaining)
                headers["RateLimit-Reset"] = str(result.reset_seconds)
            await send(message)

        await self.app(scope, receive, send_wrapper)

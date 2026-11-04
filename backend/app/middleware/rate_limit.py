"""Simple in-memory rate limiting by client IP (Phase 1)."""

from __future__ import annotations

import hashlib
import ipaddress
import math
import os
import time
from dataclasses import dataclass
from typing import Final

from pdfapp.backend.app.core.errors import problem_response
from pdfapp.backend.app.core.logging import get_logger
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = get_logger(__name__)

API_PREFIX: Final = "/api/v1"
_MAX_MEMORY_KEYS: Final = 50_000


def client_ip(headers: dict[str, str]) -> str:
    """Extract client IP from headers. Simplified: just use remote addr."""
    return headers.get("client", "127.0.0.1")


# Set by Vercel's edge on every request (client-supplied values are overwritten there).
_VERCEL_IP_HEADERS: Final = (b"x-vercel-forwarded-for", b"x-forwarded-for")


def scope_client_key(scope: Scope) -> str:
    """The rate-limit identity of a request.

    Behind Vercel the ASGI peer is Vercel's proxy, so when running on Vercel (the `VERCEL`
    env var is set) the left-most entry of Vercel's forwarding header is used instead.
    Elsewhere the headers are client-controlled and ignored. IPv6 addresses are grouped by
    /64, since one client usually owns a whole /64.
    """
    raw = ""
    if os.environ.get("VERCEL"):
        headers = dict(scope.get("headers") or [])
        for name in _VERCEL_IP_HEADERS:
            value = headers.get(name)
            if value:
                raw = value.decode("latin-1").split(",", 1)[0].strip()
                break
    if not raw:
        client = scope.get("client") or ("127.0.0.1", 0)
        raw = str(client[0])
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return "invalid"
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.IPv6Network((addr, 64), strict=False).network_address) + "/64"
    return str(addr)


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
        return self.hit_now(key)

    def hit_now(self, key: str) -> RateLimitResult:
        """Synchronous form of `hit` (no I/O, safe to call from a route)."""
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
        key = hash_client(scope_client_key(scope))

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

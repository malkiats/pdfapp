"""Redis client factories. URLs are secrets (they may embed credentials) and never logged."""

from __future__ import annotations

import redis as redis_sync
from redis.asyncio import Redis

from pdfapp.backend.app.core.config import RedisSettings


def make_async_redis(settings: RedisSettings) -> Redis | None:
    if settings.url is None:
        return None
    return Redis.from_url(
        settings.url.get_secret_value(),
        socket_timeout=settings.socket_timeout_seconds,
        socket_connect_timeout=settings.socket_timeout_seconds,
        health_check_interval=30,
    )


def make_sync_redis(settings: RedisSettings) -> redis_sync.Redis:
    """Synchronous client for RQ (which is sync). Raises if Redis is not configured.

    No read timeout: RQ workers block on BLMOVE/BLPOP for longer than any short timeout.
    """
    if settings.url is None:
        raise RuntimeError("APP_REDIS__URL is required for workers and the sweeper")
    return redis_sync.Redis.from_url(
        settings.url.get_secret_value(),
        socket_connect_timeout=settings.socket_timeout_seconds,
    )

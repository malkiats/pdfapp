"""Sweeper: scheduled, idempotent cleanup (ADR-0002) under a single-node Redis lock.

Runs as its own process (`python -m app.workers sweeper`). Every interval it tries to take
the lock; the holder calls TempFileManager.sweep_expired(). Another sweeper replica simply
skips that round. The lock has a TTL so a crashed holder cannot block cleanup.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Final

from redis.asyncio import Redis
from redis.exceptions import LockError, RedisError

from pdfapp.backend.app.core.config import Settings
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.core.redis import make_async_redis
from pdfapp.backend.app.storage import SweepReport, TempFileManager, build_temp_file_manager

log = get_logger(__name__, role="sweeper")

LOCK_NAME: Final = "lock:sweeper"


async def run_once(
    manager: TempFileManager, redis: Redis, settings: Settings
) -> SweepReport | None:
    """One sweep if the lock is free. Returns None when another sweeper holds it."""
    lock = redis.lock(LOCK_NAME, timeout=settings.queues.sweeper_lock_ttl_seconds, blocking=False)
    try:
        acquired = await lock.acquire(blocking=False)
    except (RedisError, OSError) as exc:
        log.warning("sweeper_lock_unavailable", error_class=type(exc).__name__)
        return None
    if not acquired:
        log.info("sweep_skipped", reason="locked")
        return None
    try:
        return await manager.sweep_expired(limit=settings.retention.sweep_batch_limit)
    finally:
        try:
            await lock.release()
        except (LockError, RedisError, OSError) as exc:
            log.warning("sweeper_lock_release_failed", error_class=type(exc).__name__)


async def run_forever(
    settings: Settings,
    *,
    redis: Redis | None = None,
    manager: TempFileManager | None = None,
    stop: asyncio.Event | None = None,
) -> None:
    client = redis or make_async_redis(settings.redis)
    if client is None:
        raise RuntimeError("APP_REDIS__URL is required for the sweeper")
    manager = manager or build_temp_file_manager(settings, client)
    stop = stop or asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, RuntimeError):  # non-main thread
            loop.add_signal_handler(sig, stop.set)
    log.info("sweeper_started")
    try:
        while not stop.is_set():
            try:
                await run_once(manager, client, settings)
            except Exception as exc:  # noqa: BLE001 - keep sweeping on the next round
                log.error("sweep_failed", error_class=type(exc).__name__)
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.retention.sweep_interval_seconds
                )
            except TimeoutError:
                continue
    finally:
        log.info("sweeper_stopped")
        if redis is None:
            await client.aclose()

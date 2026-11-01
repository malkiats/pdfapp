"""RQ worker processes, one per egress profile (ADR-0001).

RQ forks a fresh work-horse per job (crash and memory isolation, reliable timeout kill).
Job descriptions are not logged (they would include call arguments). On start and every
maintenance interval the worker removes stale per-job scratch directories (ADR-0002 s.5).
"""

from __future__ import annotations

import asyncio
from typing import Any

from rq import Queue, Worker

from pdfapp.backend.app.core.config import Settings
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.core.redis import make_async_redis, make_sync_redis
from pdfapp.backend.app.storage import build_temp_file_manager
from pdfapp.backend.app.workers.queues import Role, queues_for

log = get_logger(__name__)

MAINTENANCE_INTERVAL_SECONDS = 60


async def _clean_workdirs(settings: Settings) -> None:
    client = make_async_redis(settings.redis)
    try:
        removed, failures = await build_temp_file_manager(settings, client).clean_stale_workdirs()
        if removed or failures:
            log.info("workdirs_cleaned", deleted=removed, failures=failures)
    finally:
        if client is not None:
            await client.aclose()


def clean_workdirs(settings: Settings) -> None:
    try:
        asyncio.run(_clean_workdirs(settings))
    except Exception as exc:  # noqa: BLE001 - never stop the worker over housekeeping
        log.warning("workdir_cleanup_failed", error_class=type(exc).__name__)


class PrivacyWorker(Worker):
    """RQ Worker that also removes stale scratch dirs during maintenance."""

    app_settings: Settings

    def run_maintenance_tasks(self) -> None:
        super().run_maintenance_tasks()  # type: ignore[no-untyped-call]
        clean_workdirs(self.app_settings)


def build_worker(role: Role, settings: Settings, connection: Any | None = None) -> Any:
    conn = connection if connection is not None else make_sync_redis(settings.redis)
    queues = [Queue(name, connection=conn) for name in queues_for(role, settings)]
    worker = PrivacyWorker(
        queues,
        connection=conn,
        log_job_description=False,
        default_result_ttl=settings.queues.result_ttl_seconds,
        maintenance_interval=MAINTENANCE_INTERVAL_SECONDS,
    )
    worker.app_settings = settings
    return worker


def run_worker(role: Role, settings: Settings) -> bool:
    log.info("worker_starting", role=role.value)
    clean_workdirs(settings)
    worker = build_worker(role, settings)
    return bool(worker.work(logging_level=settings.logging.level))

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import fakeredis
import pytest

from pdfapp.backend.app.core.config import QueueSettings, RetentionSettings
from pdfapp.backend.app.storage import FileKind, RedisWorkspaceIndex, TempFileManager
from pdfapp.backend.app.storage.backends.local import LocalBackend
from pdfapp.backend.app.workers.__main__ import main
from pdfapp.backend.app.workers.queues import Role, queues_for
from pdfapp.backend.app.workers.runner import build_worker
from pdfapp.backend.app.workers.sweeper import LOCK_NAME, run_forever, run_once
from pdfapp.backend.tests.conftest import make_settings


async def _one(data: bytes):  # type: ignore[no-untyped-def]
    yield data


def _manager(tmp_path: Path, redis: fakeredis.FakeAsyncRedis) -> TempFileManager:
    return TempFileManager(
        LocalBackend(tmp_path / "ws-root"),
        RedisWorkspaceIndex(redis),
        retention=RetentionSettings(),
        work_dir=tmp_path / "work",
        max_job_timeout_seconds=300,
    )


async def test_sweeper_run_once_takes_lock_and_sweeps(tmp_path: Path) -> None:
    redis = fakeredis.FakeAsyncRedis()
    settings = make_settings(tmp_path)
    manager = _manager(tmp_path, redis)
    ws = await manager.create_workspace(ttl=timedelta(seconds=60))
    await manager.write_input(ws.job_id, 0, _one(b"x"), kind=FileKind.PDF, max_bytes=10)
    await manager.mark_delivered(ws.job_id, grace=timedelta(0))
    report = await run_once(manager, redis, settings)
    assert report is not None
    assert report.deleted == 1
    assert await redis.get(LOCK_NAME) is None  # released


async def test_sweeper_skips_when_lock_held(tmp_path: Path) -> None:
    redis = fakeredis.FakeAsyncRedis()
    settings = make_settings(tmp_path)
    holder = redis.lock(LOCK_NAME, timeout=60)
    assert await holder.acquire(blocking=False)
    assert await run_once(_manager(tmp_path, redis), redis, settings) is None
    await holder.release()


async def test_sweeper_loop_stops_on_event(tmp_path: Path) -> None:
    redis = fakeredis.FakeAsyncRedis()
    settings = make_settings(tmp_path, retention=RetentionSettings(sweep_interval_seconds=5))
    stop = asyncio.Event()
    task = asyncio.create_task(
        run_forever(settings, redis=redis, manager=_manager(tmp_path, redis), stop=stop)
    )
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=2)


async def test_sweeper_requires_redis(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="APP_REDIS__URL"):
        await run_forever(make_settings(tmp_path))


def test_queue_mapping(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, queues=QueueSettings(docs=["docs-paid", "docs"]))
    assert queues_for(Role.WORKER_DOCS, settings) == ["docs-paid", "docs"]
    assert queues_for(Role.WORKER_WEB, settings) == ["web"]
    assert queues_for(Role.WORKER_AI, settings) == ["ai"]
    with pytest.raises(ValueError, match="no queues"):
        queues_for(Role.SWEEPER, settings)


def test_worker_never_logs_job_descriptions(tmp_path: Path) -> None:
    worker = build_worker(
        Role.WORKER_DOCS, make_settings(tmp_path), connection=fakeredis.FakeRedis()
    )
    assert worker.log_job_description is False
    assert [q.name for q in worker.queues] == ["docs"]
    assert worker.maintenance_interval == 60


def test_entrypoint_rejects_unknown_role(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["worker-everything"]) == 2
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err


def test_entrypoint_without_redis_fails_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdfapp.backend.app.core.config import get_settings

    monkeypatch.setenv("APP_STORAGE__ROOT", str(tmp_path / "s"))
    get_settings.cache_clear()
    try:
        assert main(["sweeper"]) == 1
        assert main(["worker-docs"]) == 1
    finally:
        get_settings.cache_clear()
    assert "APP_REDIS__URL is required" in capsys.readouterr().err

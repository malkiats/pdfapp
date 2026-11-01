"""Deletion never depends on the Redis index; backend errors surface as storage errors."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from pdfapp.backend.app.core.config import RetentionSettings
from pdfapp.backend.app.storage import (
    DeletionReason,
    FileKind,
    NotFound,
    RedisWorkspaceIndex,
    StorageUnavailable,
    TempFileManager,
)
from pdfapp.backend.app.storage.backends.local import LocalBackend


class DownRedis(fakeredis.FakeAsyncRedis):
    """Every command fails like an unreachable Redis."""

    async def execute_command(self, *args: Any, **kwargs: Any) -> Any:
        raise RedisConnectionError("redis://:CANARY@host unreachable")

    def pipeline(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        raise RedisConnectionError("redis://:CANARY@host unreachable")


async def _one(data: bytes) -> AsyncIterator[bytes]:
    yield data


def _manager(tmp_path: Path, redis: fakeredis.FakeAsyncRedis) -> TempFileManager:
    return TempFileManager(
        LocalBackend(tmp_path / "s"),
        RedisWorkspaceIndex(redis),
        retention=RetentionSettings(),
        work_dir=tmp_path / "w",
        max_job_timeout_seconds=300,
    )


async def test_index_operations_wrap_redis_errors() -> None:
    index = RedisWorkspaceIndex(DownRedis())
    now = datetime.now(UTC)
    for call in (
        index.get("a" * 32),
        index.due(now, 10),
        index.reschedule("a" * 32, now),
        index.unschedule("a" * 32),
        index.tombstone("a" * 32, reason="user", ttl_seconds=10),
        index.record_failure({"job_id": "a" * 32}),
        index.failures(),
    ):
        with pytest.raises(StorageUnavailable):
            await call


async def test_delete_and_sweep_work_without_index(tmp_path: Path) -> None:
    healthy = _manager(tmp_path, fakeredis.FakeAsyncRedis())
    ws = await healthy.create_workspace()
    await healthy.write_input(ws.job_id, 0, _one(b"x"), kind=FileKind.PDF, max_bytes=10)

    degraded = _manager(tmp_path, DownRedis())
    with pytest.raises(StorageUnavailable):
        await degraded.create_workspace()
    result = await degraded.delete(ws.job_id, reason=DeletionReason.USER)
    assert result.deleted_objects == 1
    assert not list((tmp_path / "s").rglob("*.pdf"))

    report = await degraded.sweep_expired(now=datetime.now(UTC) + timedelta(hours=3))
    assert report.failures == 0
    await degraded.record_cleanup_failure(ws.job_id, stage="delete", error=OSError("x"))


async def test_tombstone_survives_record_expiry(tmp_path: Path) -> None:
    redis = fakeredis.FakeAsyncRedis()
    manager = _manager(tmp_path, redis)
    ws = await manager.create_workspace()
    await manager.delete(ws.job_id, reason=DeletionReason.FAILED)
    raw = await redis.hgetall(f"ws:{ws.job_id}")
    assert raw[b"state"] == b"deleted"
    assert raw[b"reason"] == b"failed"
    assert set(raw) <= {b"job_id", b"hour", b"created_at", b"expires_at", b"state", b"reason"}
    await redis.delete(f"ws:{ws.job_id}")
    await redis.hset(f"ws:{ws.job_id}", mapping={"state": "deleted", "reason": "failed"})
    assert await manager.get_workspace(ws.job_id) is None


async def test_local_backend_error_paths(tmp_path: Path) -> None:
    backend = LocalBackend(tmp_path / "root")
    with pytest.raises(NotFound):
        async for _ in backend.get_stream("ws/missing"):
            pass
    with pytest.raises(NotFound):
        await backend.download_to("ws/missing", tmp_path / "dest")
    assert await backend.size("ws/missing") is None
    assert await backend.list_keys("ws/none/") == []
    assert await backend.list_children("ws/none/") == []
    assert await backend.delete_prefix("ws/none/") == 0
    with pytest.raises(StorageUnavailable):
        await backend.put_file("ws/x/out/result.pdf", tmp_path / "does-not-exist")
    source = tmp_path / "src.bin"
    source.write_bytes(b"abc")
    assert await backend.put_file("ws/x/out/result.pdf", source) == 3
    dest = tmp_path / "copy.bin"
    assert await backend.download_to("ws/x/out/result.pdf", dest) == 3
    assert oct(dest.stat().st_mode & 0o777) == "0o600"


async def test_delete_prefix_failure_is_storage_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = LocalBackend(tmp_path / "root")
    await backend.put_stream("ws/2026103110/" + "a" * 32 + "/in/000.pdf", _one(b"x"), max_bytes=5)

    def denied(path: str) -> None:
        raise PermissionError(f"denied {path}")

    monkeypatch.setattr("app.storage.backends.local.os.unlink", denied)
    with pytest.raises(StorageUnavailable) as info:
        await backend.delete_prefix("ws/2026103110/")
    assert "denied" not in str(info.value)

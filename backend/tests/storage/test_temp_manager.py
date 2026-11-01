"""TempFileManager contract tests (ADR-0002), run against every index implementation.

Phase 4 adds the S3 backend; these tests then parametrize over backends as well.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import fakeredis
import pytest

from pdfapp.backend.app.core.config import RetentionSettings
from pdfapp.backend.app.core.logging import configure_logging
from pdfapp.backend.app.storage import (
    DeletionReason,
    FileKind,
    InMemoryWorkspaceIndex,
    InputTooLarge,
    InvalidJobId,
    NotFound,
    PathEscape,
    RedisWorkspaceIndex,
    StorageUnavailable,
    TempFileManager,
    WorkspaceIndex,
)
from pdfapp.backend.app.storage.backends.local import LocalBackend

T0 = datetime(2026, 10, 31, 10, 15, tzinfo=UTC)
CANARY_NAME = "CANARY-original-name-passport-scan.pdf"


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now = self.now + timedelta(**kwargs)


async def chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


@pytest.fixture(params=["memory", "redis"])
def index(request: pytest.FixtureRequest) -> WorkspaceIndex:
    if request.param == "memory":
        return InMemoryWorkspaceIndex()
    return RedisWorkspaceIndex(fakeredis.FakeAsyncRedis())


@pytest.fixture
def clock() -> Clock:
    return Clock(T0)


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "storage", tmp_path / "work"


@pytest.fixture
def manager(index: WorkspaceIndex, clock: Clock, roots: tuple[Path, Path]) -> TempFileManager:
    storage_root, work_dir = roots
    return TempFileManager(
        LocalBackend(storage_root),
        index,
        retention=RetentionSettings(),
        work_dir=work_dir,
        max_job_timeout_seconds=300,
        clock=clock,
    )


def all_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


# ------------------------------------------------------------------ create / write
async def test_create_workspace_uses_random_hex_ids(manager: TempFileManager) -> None:
    ids = {(await manager.create_workspace()).job_id for _ in range(20)}
    assert len(ids) == 20
    assert all(len(i) == 32 and all(c in "0123456789abcdef" for c in i) for i in ids)


async def test_create_workspace_deadline_capped_by_hard_ttl(manager: TempFileManager) -> None:
    ws = await manager.create_workspace(ttl=timedelta(hours=10))
    assert ws.expires_at == T0 + timedelta(hours=2)
    ws2 = await manager.create_workspace()
    assert ws2.expires_at == T0 + timedelta(hours=1)
    with pytest.raises(ValueError, match="positive"):
        await manager.create_workspace(ttl=timedelta(0))


async def test_write_input_uses_layout_and_never_filenames(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    ws = await manager.create_workspace()
    stored = await manager.write_input(
        ws.job_id, 0, chunks(b"%PDF-1.7 ", b"hello"), kind=FileKind.PDF, max_bytes=1024
    )
    assert stored.key == "in/000.pdf"
    assert stored.size_bytes == 14
    files = all_files(roots[0])
    assert files == [f"ws/2026103110/{ws.job_id}/in/000.pdf"]
    assert CANARY_NAME not in "".join(files)
    on_disk = roots[0] / files[0]
    assert on_disk.read_bytes() == b"%PDF-1.7 hello"
    assert oct(on_disk.stat().st_mode & 0o777) == "0o600"


async def test_oversize_input_rejected_and_partial_deleted(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    ws = await manager.create_workspace()
    with pytest.raises(InputTooLarge) as info:
        await manager.write_input(
            ws.job_id, 0, chunks(b"a" * 600, b"b" * 600), kind=FileKind.PDF, max_bytes=1000
        )
    assert info.value.limit_bytes == 1000
    assert all_files(roots[0]) == []


async def test_write_to_unknown_or_invalid_workspace(manager: TempFileManager) -> None:
    with pytest.raises(NotFound):
        await manager.write_input("0" * 32, 0, chunks(b"x"), kind=FileKind.PDF, max_bytes=10)
    for bad in ["../" + "0" * 29, "A" * 32, "0" * 31, "", "0" * 32 + "/x"]:
        with pytest.raises(InvalidJobId):
            await manager.write_input(bad, 0, chunks(b"x"), kind=FileKind.PDF, max_bytes=10)
    ws = await manager.create_workspace()
    with pytest.raises(ValueError, match="index"):
        await manager.write_input(ws.job_id, 1000, chunks(b"x"), kind=FileKind.PDF, max_bytes=10)


async def test_write_after_expiry_is_refused(manager: TempFileManager, clock: Clock) -> None:
    ws = await manager.create_workspace()
    clock.advance(minutes=61)
    with pytest.raises(NotFound):
        await manager.write_input(ws.job_id, 0, chunks(b"x"), kind=FileKind.PDF, max_bytes=10)


# ------------------------------------------------------------------ path escape
@pytest.mark.parametrize(
    "key", ["../outside", "ws/../../x", "/etc/passwd", "ws/./x", "ws//x", "ws\\x", "a\x00b"]
)
async def test_backend_refuses_escaping_keys(tmp_path: Path, key: str) -> None:
    backend = LocalBackend(tmp_path / "root")
    with pytest.raises(PathEscape):
        await backend.put_stream(key, chunks(b"x"), max_bytes=10)
    assert not (tmp_path / "outside").exists()


async def test_backend_refuses_symlinked_escape(tmp_path: Path) -> None:
    backend = LocalBackend(tmp_path / "root")
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "root").mkdir()
    (tmp_path / "root" / "ws").symlink_to(outside)
    with pytest.raises(PathEscape):
        await backend.put_stream("ws/x", chunks(b"x"), max_bytes=10)
    assert list(outside.iterdir()) == []


# ------------------------------------------------------------------ worker side
async def test_local_workdir_roundtrip_and_commit(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    ws = await manager.create_workspace()
    await manager.write_input(ws.job_id, 0, chunks(b"one"), kind=FileKind.PDF, max_bytes=100)
    await manager.write_input(ws.job_id, 1, chunks(b"two"), kind=FileKind.PNG, max_bytes=100)
    async with manager.local_workdir(ws.job_id) as wd:
        assert wd.root == roots[1] / ws.job_id
        assert oct(wd.root.stat().st_mode & 0o777) == "0o700"
        assert [p.name for p in wd.inputs] == ["000.pdf", "001.png"]
        assert [p.read_bytes() for p in wd.inputs] == [b"one", b"two"]
        assert wd.tmp.is_dir()
        out = manager.output_path(wd, kind=FileKind.PDF)
        assert out == wd.root / "out" / "result.pdf"
        out.write_bytes(b"%PDF-result")
        stored = await manager.commit_output(ws.job_id, out, kind=FileKind.PDF)
        assert stored.key == "out/result.pdf"
    assert not (roots[1] / ws.job_id).exists()
    obj, stream = await manager.open_output(ws.job_id)
    assert obj.kind is FileKind.PDF
    assert obj.size_bytes == 11
    assert b"".join([c async for c in stream]) == b"%PDF-result"


async def test_workdir_wiped_after_failure_inside(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    ws = await manager.create_workspace()
    await manager.write_input(ws.job_id, 0, chunks(b"data"), kind=FileKind.PDF, max_bytes=100)

    class ToolCrashedError(RuntimeError):
        pass

    async def run_tool() -> None:
        async with manager.local_workdir(ws.job_id) as wd:
            (wd.tmp / "scratch.bin").write_bytes(b"secret scratch")
            manager.output_path(wd, kind=FileKind.PDF).write_bytes(b"partial")
            raise ToolCrashedError("subprocess died")

    with pytest.raises(ToolCrashedError):
        await run_tool()
    assert not (roots[1] / ws.job_id).exists()
    result = await manager.delete(ws.job_id, reason=DeletionReason.FAILED)
    assert result.deleted_objects == 1
    assert all_files(roots[0]) == []
    assert await manager.get_workspace(ws.job_id) is None


async def test_commit_output_refuses_paths_outside_workdir(
    manager: TempFileManager, tmp_path: Path
) -> None:
    ws = await manager.create_workspace()
    outside = tmp_path / "elsewhere.pdf"
    outside.write_bytes(b"x")
    async with manager.local_workdir(ws.job_id) as wd:
        with pytest.raises(PathEscape):
            await manager.commit_output(ws.job_id, outside, kind=FileKind.PDF)
        link = wd.root / "out" / "result.pdf"
        link.symlink_to(outside)
        with pytest.raises(PathEscape):
            await manager.commit_output(ws.job_id, link, kind=FileKind.PDF)
        with pytest.raises(PathEscape):
            await manager.commit_output(ws.job_id, wd.root / "out", kind=FileKind.PDF)
        with pytest.raises(NotFound):
            await manager.commit_output(ws.job_id, wd.root / "missing.pdf", kind=FileKind.PDF)


async def test_delete_inputs_keeps_output(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    ws = await manager.create_workspace()
    await manager.write_input(ws.job_id, 0, chunks(b"in"), kind=FileKind.PDF, max_bytes=10)
    async with manager.local_workdir(ws.job_id) as wd:
        out = manager.output_path(wd, kind=FileKind.ZIP)
        out.write_bytes(b"PK")
        await manager.commit_output(ws.job_id, out, kind=FileKind.ZIP)
    result = await manager.delete_inputs(ws.job_id)
    assert result.deleted_objects == 1
    assert all_files(roots[0]) == [f"ws/2026103110/{ws.job_id}/out/result.zip"]
    again = await manager.delete_inputs(ws.job_id)
    assert again.already_absent


# ------------------------------------------------------------------ delivery / delete
async def test_mark_delivered_shortens_deadline_idempotently(
    manager: TempFileManager, clock: Clock
) -> None:
    ws = await manager.create_workspace()
    clock.advance(minutes=5)
    await manager.mark_delivered(ws.job_id)
    first = await manager.get_workspace(ws.job_id)
    assert first is not None
    assert first.expires_at == T0 + timedelta(minutes=7)
    clock.advance(minutes=1)
    await manager.mark_delivered(ws.job_id)  # never extends
    second = await manager.get_workspace(ws.job_id)
    assert second is not None
    assert second.expires_at == first.expires_at
    clock.advance(minutes=2)
    with pytest.raises(NotFound):
        await manager.open_output(ws.job_id)
    await manager.mark_delivered("f" * 32)  # unknown: no-op


async def test_delete_is_idempotent_and_honest(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    ws = await manager.create_workspace()
    await manager.write_input(ws.job_id, 0, chunks(b"a"), kind=FileKind.PDF, max_bytes=10)
    await manager.write_input(ws.job_id, 1, chunks(b"b"), kind=FileKind.PDF, max_bytes=10)
    first = await manager.delete(ws.job_id, reason=DeletionReason.USER)
    assert (first.deleted_objects, first.already_absent) == (2, False)
    second = await manager.delete(ws.job_id, reason=DeletionReason.USER)
    assert (second.deleted_objects, second.already_absent) == (0, True)
    never = await manager.delete("e" * 32, reason=DeletionReason.USER)
    assert never.already_absent
    assert all_files(roots[0]) == []
    assert await manager.get_workspace(ws.job_id) is None
    with pytest.raises(NotFound):
        await manager.open_output(ws.job_id)


async def test_delete_failure_is_recorded_and_retried(
    manager: TempFileManager, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = await manager.create_workspace()
    await manager.write_input(ws.job_id, 0, chunks(b"a"), kind=FileKind.PDF, max_bytes=10)
    backend = manager.backend
    original = backend.delete_prefix

    async def broken(prefix: str) -> int:
        raise StorageUnavailable("delete failed")

    monkeypatch.setattr(backend, "delete_prefix", broken)
    with pytest.raises(StorageUnavailable):
        await manager.delete(ws.job_id, reason=DeletionReason.USER)
    failures = await manager.cleanup_failures()
    assert failures[0]["stage"] == "delete"
    assert failures[0]["error_class"] == "StorageUnavailable"
    assert failures[0]["attempt"] == 1

    monkeypatch.setattr(backend, "delete_prefix", original)
    report = await manager.sweep_expired(now=clock.now + timedelta(seconds=1))
    assert report.deleted == 1
    assert report.failures == 0
    assert await manager.get_workspace(ws.job_id) is None


# ------------------------------------------------------------------ sweeping
async def test_sweep_deletes_expired_and_delivered(
    manager: TempFileManager, clock: Clock, roots: tuple[Path, Path]
) -> None:
    keep = await manager.create_workspace()
    expire = await manager.create_workspace(ttl=timedelta(minutes=10))
    delivered = await manager.create_workspace()
    for ws in (keep, expire, delivered):
        await manager.write_input(ws.job_id, 0, chunks(b"x"), kind=FileKind.PDF, max_bytes=10)
    await manager.mark_delivered(delivered.job_id)
    report = await manager.sweep_expired(now=T0 + timedelta(minutes=11))
    assert report.deleted == 2
    assert report.failures == 0
    assert all_files(roots[0]) == [f"ws/2026103110/{keep.job_id}/in/000.pdf"]
    # Idempotent: a second sweep finds nothing to do.
    again = await manager.sweep_expired(now=T0 + timedelta(minutes=11))
    assert again.deleted == 0


async def test_sweep_removes_orphans_without_index_after_hard_ttl(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    orphan_id = "a" * 32
    orphan_dir = roots[0] / "ws" / "2026103110" / orphan_id / "in"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "000.pdf").write_bytes(b"left behind by a crash")
    # Before the hard TTL the orphan stays.
    early = await manager.sweep_expired(now=T0 + timedelta(minutes=30))
    assert early.deleted == 0
    assert all_files(roots[0])
    report = await manager.sweep_expired(now=T0 + timedelta(hours=2, minutes=1))
    assert report.deleted == 1
    assert all_files(roots[0]) == []
    assert not (roots[0] / "ws" / "2026103110").exists()


async def test_sweep_keeps_young_workspace_in_old_bucket(
    manager: TempFileManager, clock: Clock, roots: tuple[Path, Path]
) -> None:
    clock.now = T0.replace(minute=59)
    ws = await manager.create_workspace(ttl=timedelta(hours=2))
    await manager.write_input(ws.job_id, 0, chunks(b"x"), kind=FileKind.PDF, max_bytes=10)
    report = await manager.sweep_expired(now=T0.replace(minute=0) + timedelta(hours=2, minutes=5))
    assert report.deleted == 0
    assert all_files(roots[0])


async def test_sweep_removes_stale_workdirs(
    manager: TempFileManager, roots: tuple[Path, Path]
) -> None:
    work = roots[1]
    stale = work / ("b" * 32)
    fresh = work / ("c" * 32)
    foreign = work / "not-a-job"
    for d in (stale, fresh, foreign):
        (d / "tmp").mkdir(parents=True)
        (d / "tmp" / "x").write_bytes(b"scratch")
    old = (T0 - timedelta(hours=1)).timestamp()
    os.utime(stale, (old, old))
    os.utime(foreign, (old, old))
    os.utime(fresh, (T0.timestamp(), T0.timestamp()))
    report = await manager.sweep_expired(now=T0)
    assert report.deleted == 1
    assert not stale.exists()
    assert fresh.exists()
    assert foreign.exists()


async def test_record_cleanup_failure_stores_type_only(
    manager: TempFileManager, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO", json_output=True)
    secret_path = f"/data/workspaces/{CANARY_NAME}"
    await manager.record_cleanup_failure(
        "d" * 32, stage="delete", error=PermissionError(f"denied: {secret_path}")
    )
    await manager.record_cleanup_failure("../bad", stage="Bad Stage!", error=OSError("x"))
    failures = await manager.cleanup_failures()
    serialized = json.dumps(failures)
    assert CANARY_NAME not in serialized
    assert "denied" not in serialized
    assert failures[1] == {
        "job_id": "d" * 32,
        "stage": "delete",
        "error_class": "PermissionError",
        "attempt": 1,
        "ts": T0.isoformat(),
    }
    assert failures[0]["job_id"] == "n/a"
    assert failures[0]["stage"] == "unknown"
    out = capsys.readouterr().out
    assert CANARY_NAME not in out
    assert "PermissionError" in out


async def test_record_cleanup_failure_never_raises(roots: tuple[Path, Path], clock: Clock) -> None:
    class BrokenIndex(InMemoryWorkspaceIndex):
        async def record_failure(self, entry: dict[str, object]) -> int:
            raise StorageUnavailable("index unavailable")

    mgr = TempFileManager(
        LocalBackend(roots[0]),
        BrokenIndex(),
        retention=RetentionSettings(),
        work_dir=roots[1],
        max_job_timeout_seconds=300,
        clock=clock,
    )
    await mgr.record_cleanup_failure("d" * 32, stage="delete", error=OSError("x"))


async def test_ping_reports_unwritable_storage(tmp_path: Path) -> None:
    blocker = tmp_path / "file-not-dir"
    blocker.write_bytes(b"")
    backend = LocalBackend(blocker / "root")
    with pytest.raises((StorageUnavailable, OSError)):
        await backend.ping()
    ok = LocalBackend(tmp_path / "ok")
    await ok.ping()
    assert list((tmp_path / "ok").iterdir()) == []

"""TempFileManager: the only code allowed to create, read, write or delete workspace content.

Implements the interface fixed by docs/adr/0002-temp-storage-and-cleanup.md. Names are the
contract. Summary of the guarantees:

- Workspaces are keyed by a 128-bit random ``job_id`` (``secrets.token_hex(16)``), validated
  against ``^[0-9a-f]{32}$`` on every call.
- Layout: ``ws/<YYYYMMDDHH>/<job_id>/in/<NNN>.<ext>`` and ``.../out/result.<ext>``. The
  extension comes from the sniffed ``FileKind``; original filenames are never used or stored.
- Deletion is idempotent and honest (``DeletionResult``), never depends on the Redis index
  (storage hour buckets are scanned too), and failures are recorded with the error type only.
- Worker scratch ``<work_dir>/<job_id>`` (0700) is wiped on every exit of ``local_workdir``.

Logging: only ``job_id``, layout-generated ``key``, ``kind``, ``size_bytes``, ``reason``,
``stage`` and timings.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from anyio import to_thread

from pdfapp.backend.app.core.config import RetentionSettings
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.storage.backends.base import StorageBackend
from pdfapp.backend.app.storage.errors import (
    InvalidJobId,
    NotFound,
    PathEscape,
    StorageUnavailable,
)
from pdfapp.backend.app.storage.index import WorkspaceIndex, WorkspaceRecord

log = get_logger(__name__)

_JOB_ID_RE: Final = re.compile(r"^[0-9a-f]{32}$")
_HOUR_RE: Final = re.compile(r"^[0-9]{10}$")
_STAGE_RE: Final = re.compile(r"^[a-z_]{1,32}$")
_HOUR_FMT: Final = "%Y%m%d%H"
_MAX_INPUTS: Final = 1000
_DIR_MODE: Final = 0o700
WS_ROOT: Final = "ws/"


class FileKind(StrEnum):
    """Decided by magic-byte sniffing, never by filename. The value is the file extension."""

    PDF = "pdf"
    PNG = "png"
    JPEG = "jpg"
    WEBP = "webp"
    TIFF = "tiff"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    JSON = "json"
    ZIP = "zip"  # multi-file results (contract ResultKind)


class WorkspaceState(StrEnum):
    CREATED = "created"
    READY = "ready"
    PROCESSING = "processing"
    DONE = "done"
    DELIVERED = "delivered"
    FAILED = "failed"
    DELETED = "deleted"


class DeletionReason(StrEnum):
    DELIVERED = "delivered"
    FAILED = "failed"
    USER = "user"
    EXPIRED = "expired"
    ORPHANED = "orphaned"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Workspace:
    job_id: str
    created_at: datetime
    expires_at: datetime  # current hard deadline for everything in this workspace


@dataclass(frozen=True)
class StoredObject:
    job_id: str
    key: str  # e.g. "in/000.pdf" (relative, layout-controlled)
    kind: FileKind
    size_bytes: int


@dataclass(frozen=True)
class LocalWorkdir:
    job_id: str
    root: Path  # <work_dir>/<job_id>, 0700
    inputs: list[Path]  # materialised inputs, in upload order
    tmp: Path  # TMPDIR / HOME for subprocesses


@dataclass(frozen=True)
class DeletionResult:
    job_id: str
    deleted_objects: int
    already_absent: bool  # True when nothing was left, so repeat calls are harmless


@dataclass(frozen=True)
class SweepReport:
    scanned: int
    deleted: int
    failures: int  # recorded via record_cleanup_failure, never raised
    duration_ms: int


def _utcnow() -> datetime:
    return datetime.now(UTC)


def validate_job_id(job_id: str) -> str:
    if not isinstance(job_id, str) or _JOB_ID_RE.fullmatch(job_id) is None:
        raise InvalidJobId("job id must be 32 lowercase hex characters")
    return job_id


def _hour_of(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(_HOUR_FMT)


def _hour_start(hour: str) -> datetime | None:
    if _HOUR_RE.fullmatch(hour) is None:
        return None
    try:
        return datetime.strptime(hour, _HOUR_FMT).replace(tzinfo=UTC)
    except ValueError:
        return None


class TempFileManager:
    """See module docstring and ADR-0002."""

    def __init__(
        self,
        backend: StorageBackend,
        index: WorkspaceIndex,
        *,
        retention: RetentionSettings,
        work_dir: Path,
        max_job_timeout_seconds: int,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._backend = backend
        self._index = index
        self._retention = retention
        self._work_dir = work_dir
        self._stale_workdir_after = timedelta(seconds=max_job_timeout_seconds + 60)
        self._clock = clock

    # ================================================================ helpers
    @property
    def backend(self) -> StorageBackend:
        return self._backend

    @property
    def work_dir(self) -> Path:
        return self._work_dir

    def _now(self) -> datetime:
        return self._clock()

    @staticmethod
    def _prefix(hour: str, job_id: str) -> str:
        return f"{WS_ROOT}{hour}/{job_id}/"

    async def _index_get(self, job_id: str) -> WorkspaceRecord | None:
        """Index lookup that never fails deletion paths: Redis down -> None (storage scan)."""
        try:
            return await self._index.get(job_id)
        except StorageUnavailable:
            log.warning("index_unavailable", job_id=job_id, stage="index_get")
            return None

    async def _live_record(self, job_id: str) -> WorkspaceRecord:
        record = await self._index.get(job_id)
        if record is None or record.state == WorkspaceState.DELETED:
            raise NotFound("workspace not found")
        if self._now() >= record.deadline:
            raise NotFound("workspace expired")
        return record

    async def _save(self, record: WorkspaceRecord) -> None:
        await self._index.put(record, ttl_seconds=self._retention.hard_ttl_seconds + 3600)

    async def _job_prefixes(self, job_id: str, record: WorkspaceRecord | None) -> list[str]:
        """Every storage prefix holding this job, found by index hint and bucket scan."""
        hours: set[str] = set()
        if record is not None:
            hours.add(record.hour)
        for hour in await self._backend.list_children(WS_ROOT):
            if _hour_start(hour) is None:
                continue
            if job_id in await self._backend.list_children(f"{WS_ROOT}{hour}/"):
                hours.add(hour)
        return [self._prefix(hour, job_id) for hour in sorted(hours)]

    # ================================================================ API side
    async def create_workspace(self, *, ttl: timedelta | None = None) -> Workspace:
        now = self._now()
        lifetime = ttl if ttl is not None else self._retention.output_ttl
        lifetime = min(lifetime, self._retention.hard_ttl)
        if lifetime <= timedelta(0):
            raise ValueError("ttl must be positive")
        job_id = secrets.token_hex(16)
        record = WorkspaceRecord(
            job_id=job_id,
            hour=_hour_of(now),
            created_at=now,
            expires_at=now + lifetime,
            state=WorkspaceState.CREATED,
        )
        await self._save(record)
        log.info("workspace_created", job_id=job_id)
        return Workspace(job_id=job_id, created_at=record.created_at, expires_at=record.deadline)

    async def write_input(
        self,
        job_id: str,
        index: int,
        chunks: AsyncIterator[bytes],
        *,
        kind: FileKind,
        max_bytes: int,
    ) -> StoredObject:
        """Streams to storage. Raises InputTooLarge (and deletes the partial) beyond max_bytes."""
        validate_job_id(job_id)
        if not 0 <= index < _MAX_INPUTS:
            raise ValueError("input index out of range")
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        kind = FileKind(kind)
        record = await self._live_record(job_id)
        relative = f"in/{index:03d}.{kind.value}"
        size = await self._backend.put_stream(
            self._prefix(record.hour, job_id) + relative, chunks, max_bytes=max_bytes
        )
        if record.state == WorkspaceState.CREATED:
            await self._save(replace(record, state=WorkspaceState.READY))
        log.info("input_stored", job_id=job_id, key=relative, kind=kind.value, size_bytes=size)
        return StoredObject(job_id=job_id, key=relative, kind=kind, size_bytes=size)

    async def open_output(self, job_id: str) -> tuple[StoredObject, AsyncIterator[bytes]]:
        """For download streaming. Raises NotFound if absent or expired."""
        validate_job_id(job_id)
        record = await self._live_record(job_id)
        prefix = self._prefix(record.hour, job_id)
        keys = await self._backend.list_keys(prefix + "out/")
        for key in keys:
            relative = key[len(prefix) :]
            name = relative.removeprefix("out/")
            stem, _, ext = name.partition(".")
            if stem != "result":
                continue
            try:
                kind = FileKind(ext)
            except ValueError:
                continue
            size = await self._backend.size(key)
            if size is None:
                break
            stored = StoredObject(job_id=job_id, key=relative, kind=kind, size_bytes=size)
            return stored, self._backend.get_stream(key)
        raise NotFound("output not found")

    async def mark_delivered(self, job_id: str, *, grace: timedelta | None = None) -> None:
        """Sets delete_after = now + grace (default from settings). Idempotent: a later call
        never extends an earlier deadline."""
        validate_job_id(job_id)
        record = await self._index.get(job_id)
        if record is None or record.state == WorkspaceState.DELETED:
            return
        delete_after = self._now() + (
            grace if grace is not None else self._retention.delivered_grace
        )
        if record.delete_after is not None and record.delete_after <= delete_after:
            delete_after = record.delete_after
        await self._save(replace(record, state=WorkspaceState.DELIVERED, delete_after=delete_after))
        log.info("output_delivered", job_id=job_id)

    # ================================================================ worker side
    def local_workdir(self, job_id: str) -> AbstractAsyncContextManager[LocalWorkdir]:
        """Creates <work_dir>/<job_id>, downloads inputs into it, yields, and ALWAYS wipes it."""
        validate_job_id(job_id)
        return self._local_workdir(job_id)

    @asynccontextmanager
    async def _local_workdir(self, job_id: str) -> AsyncIterator[LocalWorkdir]:
        record = await self._live_record(job_id)
        root = self._work_dir / job_id
        try:
            await to_thread.run_sync(self._prepare_workdir, root)
            prefix = self._prefix(record.hour, job_id)
            inputs: list[Path] = []
            for key in await self._backend.list_keys(prefix + "in/"):
                name = key.rsplit("/", 1)[-1]
                destination = root / "in" / name
                await self._backend.download_to(key, destination)
                inputs.append(destination)
            await self._save(replace(record, state=WorkspaceState.PROCESSING))
            yield LocalWorkdir(job_id=job_id, root=root, inputs=inputs, tmp=root / "tmp")
        finally:
            try:
                await to_thread.run_sync(self._wipe_dir, root)
            except OSError as exc:
                await self.record_cleanup_failure(job_id, stage="workdir", error=exc)

    def _prepare_workdir(self, root: Path) -> None:
        self._work_dir.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
        if root.exists() or root.is_symlink():
            self._wipe_dir(root)
        root.mkdir(mode=_DIR_MODE)
        for sub in ("in", "out", "tmp"):
            (root / sub).mkdir(mode=_DIR_MODE)

    @staticmethod
    def _wipe_dir(root: Path) -> None:
        if root.is_symlink():
            root.unlink()
            return
        if root.exists():
            shutil.rmtree(root)

    def output_path(self, workdir: LocalWorkdir, *, kind: FileKind) -> Path:
        """Returns workdir.root / 'out' / f'result.{kind}'. The only path a service may write
        output to."""
        return workdir.root / "out" / f"result.{FileKind(kind).value}"

    async def commit_output(self, job_id: str, path: Path, *, kind: FileKind) -> StoredObject:
        """Path must resolve inside the job's workdir. Uploads it as out/result.<ext>."""
        validate_job_id(job_id)
        kind = FileKind(kind)
        workdir = self._work_dir / job_id

        def _resolve() -> tuple[Path, bool]:
            root = workdir.resolve()
            resolved = path.resolve(strict=True)
            return resolved, resolved.is_relative_to(root) and resolved.is_file()

        try:
            resolved, inside = await to_thread.run_sync(_resolve)
        except FileNotFoundError as exc:
            raise NotFound("output file not found") from exc
        if not inside:
            raise PathEscape("output must be a regular file inside the job workdir")
        record = await self._live_record(job_id)
        prefix = self._prefix(record.hour, job_id)
        await self._backend.delete_prefix(prefix + "out/")
        relative = f"out/result.{kind.value}"
        size = await self._backend.put_file(prefix + relative, resolved)
        await self._save(replace(record, state=WorkspaceState.DONE))
        log.info("output_stored", job_id=job_id, key=relative, kind=kind.value, size_bytes=size)
        return StoredObject(job_id=job_id, key=relative, kind=kind, size_bytes=size)

    async def delete_inputs(self, job_id: str) -> DeletionResult:
        validate_job_id(job_id)
        record = await self._index_get(job_id)
        deleted = 0
        try:
            for prefix in await self._job_prefixes(job_id, record):
                deleted += await self._backend.delete_prefix(prefix + "in/")
        except StorageUnavailable as exc:
            await self.record_cleanup_failure(job_id, stage="delete_inputs", error=exc)
            raise
        log.info("inputs_deleted", job_id=job_id, deleted_objects=deleted)
        return DeletionResult(job_id=job_id, deleted_objects=deleted, already_absent=deleted == 0)

    # ================================================================ both / maintenance
    async def get_workspace(self, job_id: str) -> Workspace | None:
        validate_job_id(job_id)
        record = await self._index.get(job_id)
        if record is None or record.state == WorkspaceState.DELETED:
            return None
        return Workspace(job_id=job_id, created_at=record.created_at, expires_at=record.deadline)

    async def delete(self, job_id: str, *, reason: DeletionReason) -> DeletionResult:
        """Removes every object and the index entry. Idempotent; never raises on 'already
        gone'. Raises StorageUnavailable (after recording the failure and scheduling a retry)
        when storage could not delete everything."""
        validate_job_id(job_id)
        reason = DeletionReason(reason)
        record = await self._index_get(job_id)
        deleted = 0
        try:
            for prefix in await self._job_prefixes(job_id, record):
                deleted += await self._backend.delete_prefix(prefix)
        except StorageUnavailable as exc:
            await self.record_cleanup_failure(job_id, stage="delete", error=exc)
            try:
                await self._index.reschedule(job_id, self._now())
            except StorageUnavailable:
                log.warning("index_unavailable", job_id=job_id, stage="reschedule")
            raise
        try:
            await self._index.tombstone(
                job_id, reason=reason.value, ttl_seconds=self._retention.tombstone_ttl_seconds
            )
        except StorageUnavailable:
            # Content is gone; a stale index entry is harmless (the next sweep finds nothing).
            log.warning("index_unavailable", job_id=job_id, stage="tombstone")
        index_had_entry = record is not None and record.state != WorkspaceState.DELETED
        already_absent = deleted == 0 and not index_had_entry
        log.info("workspace_deleted", job_id=job_id, reason=reason.value, deleted_objects=deleted)
        return DeletionResult(job_id=job_id, deleted_objects=deleted, already_absent=already_absent)

    async def sweep_expired(self, *, now: datetime | None = None, limit: int = 1000) -> SweepReport:
        """Idempotent and safe to run concurrently (the caller holds a Redis lock).
        Order: (1) ws:expiry entries due; (2) storage hour-buckets older than hard_ttl,
        whether or not an index entry exists; (3) local work-dir leftovers when present."""
        started = time.monotonic()
        moment = now or self._now()
        scanned = deleted = failures = 0

        # (1) index entries whose deadline has passed
        try:
            due = await self._index.due(moment, limit)
        except StorageUnavailable:
            log.warning("index_unavailable", stage="sweep_due")
            due = []
        for job_id in due:
            scanned += 1
            if _JOB_ID_RE.fullmatch(job_id) is None:
                continue
            record = await self._index_get(job_id)
            reason = (
                DeletionReason.DELIVERED
                if record is not None and record.state == WorkspaceState.DELIVERED
                else DeletionReason.EXPIRED
            )
            outcome = await self._sweep_one(job_id, reason)
            deleted += outcome[0]
            failures += outcome[1]

        # (2) hour buckets old enough that anything in them may be past the hard TTL
        cutoff = moment - self._retention.hard_ttl
        try:
            hours = await self._backend.list_children(WS_ROOT)
        except (StorageUnavailable, OSError) as exc:
            await self.record_cleanup_failure("sweep", stage="list_buckets", error=exc)
            hours = []
            failures += 1
        for hour in hours:
            start = _hour_start(hour)
            if start is None or start > cutoff:
                continue
            bucket = f"{WS_ROOT}{hour}/"
            for job_id in await self._backend.list_children(bucket):
                if _JOB_ID_RE.fullmatch(job_id) is None:
                    continue
                scanned += 1
                record = await self._index_get(job_id)
                live = record is not None and record.state != WorkspaceState.DELETED
                if (
                    live
                    and record is not None
                    and record.created_at + self._retention.hard_ttl > moment
                ):
                    continue  # bucket is old but this workspace is not yet past the hard TTL
                reason = DeletionReason.EXPIRED if live else DeletionReason.ORPHANED
                outcome = await self._sweep_one(job_id, reason)
                deleted += outcome[0]
                failures += outcome[1]
            if not await self._backend.list_children(bucket):
                try:
                    await self._backend.delete_prefix(bucket)
                except StorageUnavailable as exc:
                    await self.record_cleanup_failure("sweep", stage="bucket", error=exc)
                    failures += 1

        # (3) worker scratch leftovers
        removed, workdir_failures = await self.clean_stale_workdirs(now=moment)
        deleted += removed
        failures += workdir_failures

        report = SweepReport(
            scanned=scanned,
            deleted=deleted,
            failures=failures,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        log.info(
            "sweep_finished",
            scanned=report.scanned,
            deleted=report.deleted,
            failures=report.failures,
            duration_ms=report.duration_ms,
        )
        return report

    async def _sweep_one(self, job_id: str, reason: DeletionReason) -> tuple[int, int]:
        """Returns (deleted, failures) for one workspace. Never raises."""
        try:
            result = await self.delete(job_id, reason=reason)
        except StorageUnavailable:
            return 0, 1  # already recorded by delete()
        except Exception as exc:  # noqa: BLE001 - the sweeper must keep going
            await self.record_cleanup_failure(job_id, stage="sweep", error=exc)
            return 0, 1
        return (0 if result.already_absent else 1), 0

    async def clean_stale_workdirs(self, *, now: datetime | None = None) -> tuple[int, int]:
        """Removes <work_dir>/<job_id> directories older than the max job timeout (crash
        leftovers). Called by workers on start and periodically, and by sweep_expired.
        Returns (removed, failures)."""
        moment = now or self._now()
        threshold = (moment - self._stale_workdir_after).timestamp()

        def _candidates() -> list[Path]:
            try:
                entries = list(os.scandir(self._work_dir))
            except FileNotFoundError:
                return []
            stale: list[Path] = []
            for entry in entries:
                if _JOB_ID_RE.fullmatch(entry.name) is None:
                    continue
                try:
                    mtime = entry.stat(follow_symlinks=False).st_mtime
                except FileNotFoundError:
                    continue
                if mtime < threshold:
                    stale.append(Path(entry.path))
            return stale

        removed = failures = 0
        for path in await to_thread.run_sync(_candidates):
            try:
                await to_thread.run_sync(self._wipe_dir, path)
                removed += 1
                log.info("workdir_removed", job_id=path.name, reason=DeletionReason.ORPHANED.value)
            except OSError as exc:
                failures += 1
                await self.record_cleanup_failure(path.name, stage="workdir", error=exc)
        return removed, failures

    async def record_cleanup_failure(
        self, job_id: str, *, stage: str, error: BaseException
    ) -> None:
        """Stores only the type name of the error, never its message (messages can contain
        paths). Never raises."""
        safe_job = job_id if _JOB_ID_RE.fullmatch(job_id or "") else "n/a"
        safe_stage = stage if _STAGE_RE.fullmatch(stage or "") else "unknown"
        error_class = type(error).__name__
        entry = {
            "job_id": safe_job,
            "stage": safe_stage,
            "error_class": error_class,
            "ts": self._now().isoformat(),
        }
        attempt: int | None = None
        try:
            attempt = await self._index.record_failure(entry)
        except Exception:  # noqa: BLE001 - recording must never raise
            log.warning("cleanup_failure_not_recorded", job_id=safe_job, stage=safe_stage)
        log.warning(
            "cleanup_failed",
            job_id=safe_job,
            stage=safe_stage,
            error_class=error_class,
            attempt=attempt,
        )

    async def cleanup_failures(self, limit: int = 100) -> list[dict[str, object]]:
        """Recorded cleanup failures, newest first (metrics / admin tooling)."""
        return await self._index.failures(limit)

    async def ping(self) -> None:
        """Readiness check of the storage backend. Raises StorageUnavailable."""
        await self._backend.ping()

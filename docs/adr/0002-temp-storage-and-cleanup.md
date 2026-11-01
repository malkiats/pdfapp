# ADR-0002: Temp storage, TempFileManager interface and cleanup

Status: superseded by [ADR-0006](0006-synchronous-processing-on-vercel.md) on 2026-11-01 (job workspaces, Redis index and worker scratch replaced by a request-scoped `scratch()` helper) · Date: 2026-10-31

## Context
The privacy promise depends on every byte of user content following one lifecycle: validate → isolated workspace keyed by a random id → process → short-lived delivery → delete → scheduled sweep for anything left behind. If services each handle files their own way, the guarantees will drift. The API and the workers run as separate services (architecture.md §5).

## Decision
1. **A single `TempFileManager`** in `backend/app/storage/temp_manager.py` is the only code allowed to create, read, write or delete workspace content. Services receive local `Path`s from it and return output `Path`s to it. CI bans `tempfile` and `boto3` imports outside `app/storage/`.
2. **Backends** (`storage/backends/`): `LocalBackend` (shared volume; local dev, CI and single-host setups) and `S3Backend` (production; any S3-compatible private bucket). Selected by `APP_STORAGE__BACKEND`.
3. **Layout**: `ws/<YYYYMMDDHH>/<job_id>/in/<NNN>.<ext>` and `ws/<YYYYMMDDHH>/<job_id>/out/result.<ext>` (`result.zip` for multi-file outputs). `job_id` is 128 bits from `secrets.token_hex(16)`, validated against `^[0-9a-f]{32}$` on every call. `ext` is derived from the **sniffed** file kind, never from the user's filename. The hour bucket lets the sweeper find orphans without any index.
4. **Index**: Redis hash `ws:<job_id>` (created_at, hour, expires_at, state, delete_after) plus ZSET `ws:expiry` scored by deletion deadline. Both are TTL'd. The index speeds up deletion, but correctness never depends on it.
5. **Worker scratch**: `/work/<job_id>/` (tmpfs, mode 0700), wiped on context exit. Leftovers older than the max job timeout are removed when the worker starts and every 60 s.
6. **Deletion deadlines** (all from settings): inputs are deleted as soon as processing ends. **Failed jobs** have all files deleted immediately. Only a content-free Redis tombstone (`status=failed`, `error_code`) is kept for `failed_tombstone_ttl` (default 5 min) so the UI can show the error. Outputs are deleted at `min(first_completed_download + 2 min, created + 60 min)`. Every prefix is force-deleted once its hour bucket is older than 2 h. A bucket lifecycle rule expires `ws/` objects after 1 day as the last backstop.
7. **No backups**: bucket versioning off, no replication, excluded from backup plans. Redis runs without persistence or snapshots.
8. **Cleanup failures** are recorded as `{job_id, stage, error_class, attempt, ts}` (Redis list now, Postgres `app.cleanup_failures` from Phase 7), exposed as a metric, and retried on every sweep. No filenames, paths outside the layout, or content.

## Interface (implement exactly; names are the contract)

```python
# backend/app/storage/temp_manager.py  (stub: signatures only)
from enum import StrEnum
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator, Protocol
from contextlib import AbstractAsyncContextManager

class FileKind(StrEnum):        # decided by magic-byte sniffing, never by filename
    PDF = "pdf"; PNG = "png"; JPEG = "jpg"; WEBP = "webp"; TIFF = "tiff"
    DOCX = "docx"; XLSX = "xlsx"; PPTX = "pptx"; TXT = "txt"; MD = "md"; HTML = "html"; JSON = "json"
    ZIP = "zip"                 # multi-file outputs (split, PDF to images): out/result.zip

class WorkspaceState(StrEnum):
    CREATED = "created"; READY = "ready"; PROCESSING = "processing"
    SUCCEEDED = "succeeded"; DELIVERED = "delivered"; FAILED = "failed"; DELETED = "deleted"

class DeletionReason(StrEnum):
    DELIVERED = "delivered"; FAILED = "failed"; USER = "user"
    EXPIRED = "expired"; ORPHANED = "orphaned"; CANCELLED = "cancelled"

@dataclass(frozen=True)
class Workspace:
    job_id: str
    created_at: datetime
    expires_at: datetime        # hard deadline for everything in this workspace

@dataclass(frozen=True)
class StoredObject:
    job_id: str
    key: str                    # e.g. "in/000.pdf" (relative, layout-controlled)
    kind: FileKind
    size_bytes: int

@dataclass(frozen=True)
class LocalWorkdir:
    job_id: str
    root: Path                  # /work/<job_id>, 0700
    inputs: list[Path]          # materialised inputs, in upload order
    tmp: Path                   # TMPDIR / HOME for subprocesses

@dataclass(frozen=True)
class DeletionResult:
    job_id: str
    deleted_objects: int
    already_absent: bool        # True when nothing was left, so repeat calls are harmless

@dataclass(frozen=True)
class SweepReport:
    scanned: int
    deleted: int
    failures: int               # recorded via record_cleanup_failure, never raised
    duration_ms: int

class TempFileManager(Protocol):
    # --- API side ---
    async def create_workspace(self, *, ttl: timedelta | None = None) -> Workspace: ...
    async def write_input(self, job_id: str, index: int, chunks: AsyncIterator[bytes],
                          *, kind: FileKind, max_bytes: int) -> StoredObject:
        """Streams to storage. Raises InputTooLarge (and deletes the partial) beyond max_bytes."""
    async def open_output(self, job_id: str) -> tuple[StoredObject, AsyncIterator[bytes]]:
        """For download streaming. Raises NotFound if absent or expired."""
    async def mark_delivered(self, job_id: str, *, grace: timedelta | None = None) -> None:
        """Sets delete_after = now + grace (default from settings). Idempotent."""

    # --- worker side ---
    def local_workdir(self, job_id: str) -> AbstractAsyncContextManager[LocalWorkdir]:
        """Creates /work/<job_id>, downloads inputs into it, yields, and ALWAYS wipes it on exit."""
    def output_path(self, workdir: LocalWorkdir, *, kind: FileKind) -> Path:
        """Returns workdir.root / 'out' / f'result.{kind}'. The only path a service may write output to.
        Multi-file results are packed by the worker into a single result.zip (kind=ZIP)."""
    async def commit_output(self, job_id: str, path: Path, *, kind: FileKind) -> StoredObject:
        """Path must resolve inside the job's workdir. Uploads it as out/result.<ext>."""
    async def delete_inputs(self, job_id: str) -> DeletionResult: ...

    # --- both / maintenance ---
    async def get_workspace(self, job_id: str) -> Workspace | None: ...
    async def delete(self, job_id: str, *, reason: DeletionReason) -> DeletionResult:
        """Removes every object and the index entry. Idempotent; never raises on 'already gone'."""
    async def sweep_expired(self, *, now: datetime | None = None, limit: int = 1000) -> SweepReport:
        """Idempotent and safe to run concurrently (the caller holds a Redis lock).
        Order: (1) ws:expiry entries due; (2) storage hour-buckets older than hard_ttl,
        whether or not an index entry exists; (3) local /work leftovers when run in a worker."""
    async def record_cleanup_failure(self, job_id: str, *, stage: str, error: BaseException) -> None:
        """Stores only the type name of the error, never its message (messages can contain paths)."""
```

Errors (in `storage/errors.py`): `InvalidJobId`, `InputTooLarge`, `NotFound`, `PathEscape`, `StorageUnavailable`.

Logging: these methods log only `job_id`, object key (layout-generated), `kind`, `size_bytes`, `reason` and timings.

## Consequences
- (+) The privacy behaviour has one implementation, tested once by a contract suite that runs against both backends.
- (+) Crash safety comes from three independent layers: the index, the hour-bucket scan, and the bucket lifecycle rule.
- (−) Production downloads stream through the API (bandwidth on the API). This is the price of a "delivered" event we can observe and of never exposing storage URLs.
- (−) The first download starts a 2-minute grace period, so a user who comes back after that must re-run the job. Shown in the UI.

## Rejected
- **API and worker sharing a pod volume in production**: couples scaling and placement, and has no lifecycle backstop.
- **Presigned S3 GET URLs for download**: we cannot know when delivery has completed, and the URL is a bearer credential that may be logged by third parties.
- **Per-service `tempfile` usage**: impossible to audit.

"""Temporary workspace storage (ADR-0002). The only package that touches workspace bytes."""

from __future__ import annotations

from redis.asyncio import Redis

from pdfapp.backend.app.core.config import Settings
from pdfapp.backend.app.storage.backends import build_backend
from pdfapp.backend.app.storage.errors import (
    InputTooLarge,
    InvalidJobId,
    NotFound,
    PathEscape,
    StorageError,
    StorageUnavailable,
)
from pdfapp.backend.app.storage.index import InMemoryWorkspaceIndex, RedisWorkspaceIndex, WorkspaceIndex
from pdfapp.backend.app.storage.temp_manager import (
    DeletionReason,
    DeletionResult,
    FileKind,
    LocalWorkdir,
    StoredObject,
    SweepReport,
    TempFileManager,
    Workspace,
    WorkspaceState,
)


def build_temp_file_manager(settings: Settings, redis: Redis | None) -> TempFileManager:
    """Wires the configured backend and index. Without Redis the index is process-local,
    which is only suitable for tests and single-process local runs (prod requires Redis)."""
    index: WorkspaceIndex = (
        RedisWorkspaceIndex(redis) if redis is not None else InMemoryWorkspaceIndex()
    )
    return TempFileManager(
        build_backend(settings.storage),
        index,
        retention=settings.retention,
        work_dir=settings.storage.work_dir,
        max_job_timeout_seconds=settings.limits.max_job_timeout_seconds,
    )


__all__ = [
    "DeletionReason",
    "DeletionResult",
    "FileKind",
    "InMemoryWorkspaceIndex",
    "InputTooLarge",
    "InvalidJobId",
    "LocalWorkdir",
    "NotFound",
    "PathEscape",
    "RedisWorkspaceIndex",
    "StorageError",
    "StorageUnavailable",
    "StoredObject",
    "SweepReport",
    "TempFileManager",
    "Workspace",
    "WorkspaceState",
    "build_temp_file_manager",
]

"""The storage backend port (ADR-0002).

Keys are relative, layout-generated strings such as ``ws/2026103112/<job_id>/in/000.pdf``.
Only ``TempFileManager`` builds keys; backends must still refuse any key that would escape
their root (``PathEscape``) as defence in depth.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    name: str

    async def put_stream(self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int) -> int:
        """Writes the stream to ``key`` and returns its size. Raises ``InputTooLarge`` once
        more than ``max_bytes`` arrive, after deleting the partial object."""
        ...

    async def put_file(self, key: str, source: Path) -> int:
        """Copies a local file to ``key`` and returns its size."""
        ...

    def get_stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        """Streams the object. Raises ``NotFound`` (on first iteration) if absent."""
        ...

    async def download_to(self, key: str, dest: Path) -> int:
        """Copies the object into a local file (created 0600). Returns its size."""
        ...

    async def size(self, key: str) -> int | None:
        """Size in bytes, or None when absent."""
        ...

    async def list_keys(self, prefix: str) -> list[str]:
        """All object keys under ``prefix`` (which ends with '/'), sorted."""
        ...

    async def delete_prefix(self, prefix: str) -> int:
        """Deletes every object under ``prefix``. Returns the number deleted (0 if none).
        Idempotent. Raises ``StorageUnavailable`` if something could not be deleted."""
        ...

    async def list_children(self, prefix: str) -> list[str]:
        """Immediate child names under ``prefix`` (directories / common prefixes)."""
        ...

    async def ping(self) -> None:
        """Raises ``StorageUnavailable`` when the backend cannot read and write."""
        ...

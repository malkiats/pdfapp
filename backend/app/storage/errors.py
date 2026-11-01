"""Storage errors (ADR-0002). Messages never contain paths, filenames or content."""

from __future__ import annotations


class StorageError(Exception):
    """Base class for TempFileManager errors."""


class InvalidJobId(StorageError):  # noqa: N818 - name fixed by ADR-0002
    """The job id does not match ^[0-9a-f]{32}$."""


class InputTooLarge(StorageError):  # noqa: N818 - name fixed by ADR-0002
    """An input exceeded max_bytes. The partial object has been deleted."""

    def __init__(self, limit_bytes: int) -> None:
        super().__init__("input exceeds the size limit")
        self.limit_bytes = limit_bytes


class NotFound(StorageError):  # noqa: N818 - name fixed by ADR-0002
    """The workspace or object does not exist, or has expired."""


class PathEscape(StorageError):  # noqa: N818 - name fixed by ADR-0002
    """A path resolved outside the area it must stay in."""


class StorageUnavailable(StorageError):  # noqa: N818 - name fixed by ADR-0002
    """The storage backend or index could not complete the operation."""

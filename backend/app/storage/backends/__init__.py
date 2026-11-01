"""Storage backends behind the StorageBackend port.

Registered backends: ``local``. The ``s3`` backend is added in Phase 4 as a new module
implementing the same ``StorageBackend`` protocol and registered in ``build_backend``; no
other code changes are needed. It is deliberately not registered (or stubbed) before then.
"""

from __future__ import annotations

from pdfapp.backend.app.core.config import StorageSettings
from pdfapp.backend.app.storage.backends.base import StorageBackend
from pdfapp.backend.app.storage.backends.local import LocalBackend


def build_backend(settings: StorageSettings) -> StorageBackend:
    if settings.backend == "local":
        return LocalBackend(settings.root)
    raise ValueError("unsupported storage backend")  # pragma: no cover - Literal-guarded


__all__ = ["LocalBackend", "StorageBackend", "build_backend"]

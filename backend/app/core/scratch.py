"""Temporary file management for request-scoped processing.

Create a scratch directory at request start, process files in it, return results,
and clean up before the response ends.
"""

from __future__ import annotations

import shutil
import tempfile  # noqa: TID251 - phase 1 has no app.storage
from pathlib import Path


def create_scratch_dir() -> Path:
    """Create a temporary directory for this request."""
    temp_dir = tempfile.mkdtemp(prefix="tool_")
    return Path(temp_dir)


def cleanup_scratch_dir(scratch_dir: Path) -> None:
    """Remove the scratch directory and all its contents."""
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir, ignore_errors=True)

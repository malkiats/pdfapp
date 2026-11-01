"""Compress PDF file."""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def compress_pdf(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Compress PDF using pikepdf."""
    if len(files) != 1:
        raise ApiError(400, "too_many_files", detail="Compress requires exactly one file.")

    options = options or {}
    level = options.get("level", "medium")

    if level not in ("low", "medium", "high"):
        raise ApiError(400, "validation_error", detail="Level must be low, medium, or high.")

    try:
        # Open PDF with pikepdf
        pdf = pikepdf.open(io.BytesIO(files[0]))

        # Write with compression
        output = io.BytesIO()
        pdf.save(output, compress_streams=True, remove_unused_objects=True)
        output.seek(0)

        result = output.read()
        log.info("compress_pdf_success", output_size=len(result))
        return result

    except ApiError:
        raise
    except Exception as e:
        log.error("compress_pdf_failed", error_class=type(e).__name__)
        raise ApiError(500, "processing_failed", detail="Could not compress PDF.") from e

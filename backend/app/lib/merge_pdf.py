"""Merge PDF files."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def merge_pdf(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Merge multiple PDF files into one.

    Args:
        files: List of PDF bytes
        options: {"keep_bookmarks": bool} or null
        scratch_dir: Temp directory for intermediate files (not used)

    Returns:
        Merged PDF bytes
    """
    if not files or len(files) < 2:
        raise ApiError(400, "too_many_files", detail="At least 2 files are required.")

    if len(files) > 20:
        raise ApiError(400, "too_many_files", detail="Maximum 20 files allowed.")

    options = options or {}

    try:
        # Create a writer
        writer = PdfWriter()

        # Add each file in order
        for file_bytes in files:
            try:
                reader = PdfReader(io.BytesIO(file_bytes))
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as e:
                raise ApiError(
                    400,
                    "invalid_file",
                    detail="One of the files could not be read as a valid PDF.",
                ) from e

        # Write output
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        result = output.read()
        log.info("merge_pdf_success", output_size=len(result))
        return result

    except ApiError:
        raise
    except Exception as e:
        log.error("merge_pdf_failed", error_class=type(e).__name__)
        raise ApiError(
            500,
            "processing_failed",
            detail="The files could not be processed.",
        ) from e

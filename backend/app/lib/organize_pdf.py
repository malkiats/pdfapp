"""Organize PDF pages: reorder and delete."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def organize_pdf(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Reorder and delete pages from PDF."""
    if len(files) != 1:
        raise ApiError(400, "too_many_files", detail="Organize requires exactly one file.")

    options = options or {}
    page_order = options.get("page_order", [])

    if not page_order:
        raise ApiError(400, "validation_error", detail="page_order is required.")

    try:
        reader = PdfReader(io.BytesIO(files[0]))
        writer = PdfWriter()

        # Add pages in specified order (1-based to 0-based)
        for page_num in page_order:
            if not isinstance(page_num, int) or page_num < 1 or page_num > len(
                reader.pages
            ):
                raise ValueError(f"Invalid page number: {page_num}")
            writer.add_page(reader.pages[page_num - 1])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        result = output.read()
        log.info("organize_pdf_success", output_size=len(result))
        return result

    except ApiError:
        raise
    except Exception as e:
        log.error("organize_pdf_failed", error_class=type(e).__name__)
        raise ApiError(500, "processing_failed", detail="Could not organize PDF.") from e

"""Rotate PDF pages."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def rotate_pdf(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Rotate PDF pages by specified angle."""
    if len(files) != 1:
        raise ApiError(400, "too_many_files", detail="Rotate requires exactly one file.")

    options = options or {}
    angle = options.get("angle", 90)
    pages = options.get("pages")  # Optional: specific page range

    if angle not in (90, 180, 270):
        raise ApiError(400, "validation_error", detail="Angle must be 90, 180, or 270.")

    try:
        reader = PdfReader(io.BytesIO(files[0]))
        writer = PdfWriter()

        # Parse page range or use all
        if pages:
            page_indices = _parse_ranges(pages, len(reader.pages))
        else:
            page_indices = list(range(len(reader.pages)))

        # Rotate specified pages
        for i, page in enumerate(reader.pages):
            if i in page_indices:
                page.rotate_clockwise(angle)
            writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        result = output.read()
        log.info("rotate_pdf_success", output_size=len(result))
        return result

    except ApiError:
        raise
    except Exception as e:
        log.error("rotate_pdf_failed", error_class=type(e).__name__)
        raise ApiError(500, "processing_failed", detail="Could not rotate PDF.") from e


def _parse_ranges(ranges_str: str, total_pages: int) -> set[int]:
    """Parse range string into 0-based page indices."""
    pages: set[int] = set()
    for part in ranges_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start.strip()) - 1
            end = int(end.strip()) - 1
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part.strip()) - 1)
    return {p for p in pages if 0 <= p < total_pages}

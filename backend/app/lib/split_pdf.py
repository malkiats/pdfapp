"""Split PDF into individual pages."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def split_pdf(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Split PDF into individual pages, return ZIP."""
    if len(files) != 1:
        raise ApiError(400, "too_many_files", detail="Split requires exactly one file.")

    options = options or {}
    ranges = options.get("ranges")
    every_n = options.get("every_n")

    if not ranges and not every_n:
        raise ApiError(
            400, "validation_error", detail="Either ranges or every_n is required."
        )

    try:
        reader = PdfReader(io.BytesIO(files[0]))
        total_pages = len(reader.pages)

        # Parse page ranges or split every N
        if ranges:
            pages = _parse_ranges(ranges, total_pages)
        else:
            pages = list(range(0, total_pages, every_n or 1))

        if not pages:
            raise ValueError("No pages selected")

        # Create ZIP with one PDF per page
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for idx, page_num in enumerate(pages, 1):
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num])
                pdf_buffer = io.BytesIO()
                writer.write(pdf_buffer)
                pdf_buffer.seek(0)
                zf.writestr(f"part-{idx:03d}.pdf", pdf_buffer.read())

        zip_buffer.seek(0)
        result = zip_buffer.read()
        log.info("split_pdf_success", output_size=len(result), page_count=len(pages))
        return result

    except ApiError:
        raise
    except Exception as e:
        log.error("split_pdf_failed", error_class=type(e).__name__)
        raise ApiError(500, "processing_failed", detail="Could not split PDF.") from e


def _parse_ranges(ranges_str: str, total_pages: int) -> list[int]:
    """Parse range string like '1-3,5,8-10' into 0-based page indices."""
    pages: list[int] = []
    for part in ranges_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start.strip()) - 1  # 1-based to 0-based
            end = int(end.strip()) - 1
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part.strip()) - 1)
    return [p for p in pages if 0 <= p < total_pages]

"""Extract text from PDF."""

from __future__ import annotations

import io
from pathlib import Path

import pdfplumber

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def extract_text(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Extract text from PDF using pdfplumber."""
    if len(files) != 1:
        raise ApiError(400, "too_many_files", detail="Extract text requires exactly one file.")

    options = options or {}
    pages = options.get("pages")

    try:
        with pdfplumber.open(io.BytesIO(files[0])) as pdf:
            total_pages = len(pdf)

            # Parse page range or use all
            page_indices = _parse_ranges(pages, total_pages) if pages else list(range(total_pages))

            # Extract text from pages
            text_parts = []
            for page_num in page_indices:
                page = pdf.pages[page_num]
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            result = "\n\n---\n\n".join(text_parts).encode("utf-8")
            log.info("extract_text_success", output_size=len(result))
            return result

    except ApiError:
        raise
    except Exception as e:
        log.error("extract_text_failed", error_class=type(e).__name__)
        raise ApiError(500, "processing_failed", detail="Could not extract text from PDF.") from e


def _parse_ranges(ranges_str: str, total_pages: int) -> list[int]:
    """Parse range string into 0-based page indices."""
    pages: list[int] = []
    for part in ranges_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start.strip()) - 1
            end = int(end.strip()) - 1
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part.strip()) - 1)
    return [p for p in pages if 0 <= p < total_pages]

"""Convert PDF pages to images."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pypdfium2 as pdfium

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def pdf_to_images(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Convert PDF pages to images, return ZIP."""
    if len(files) != 1:
        raise ApiError(400, "too_many_files", detail="PDF to images requires exactly one file.")

    options = options or {}
    fmt = options.get("format", "png").lower()
    dpi = options.get("dpi", 150)
    pages = options.get("pages")

    if fmt not in ("png", "jpg"):
        raise ApiError(400, "validation_error", detail="Format must be png or jpg.")

    if not (72 <= dpi <= 300):
        raise ApiError(400, "validation_error", detail="DPI must be between 72 and 300.")

    try:
        # Open PDF
        pdf = pdfium.PdfDocument.new_from_file(io.BytesIO(files[0]))
        total_pages = len(pdf)

        # Parse page range or use all
        page_indices = _parse_ranges(pages, total_pages) if pages else list(range(total_pages))

        # Render to images and zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for idx, page_num in enumerate(page_indices, 1):
                page = pdf.get_page(page_num)
                bitmap = page.render(dpi=dpi).to_pil()

                img_buffer = io.BytesIO()
                if fmt == "png":
                    bitmap.save(img_buffer, format="PNG")
                    filename = f"page-{idx:03d}.png"
                else:
                    bitmap.convert("RGB").save(img_buffer, format="JPEG")
                    filename = f"page-{idx:03d}.jpg"

                img_buffer.seek(0)
                zf.writestr(filename, img_buffer.read())

        zip_buffer.seek(0)
        result = zip_buffer.read()
        log.info("pdf_to_images_success", output_size=len(result), page_count=len(page_indices))
        return result

    except ApiError:
        raise
    except Exception as e:
        log.error("pdf_to_images_failed", error_class=type(e).__name__)
        raise ApiError(500, "processing_failed", detail="Could not convert PDF to images.") from e


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

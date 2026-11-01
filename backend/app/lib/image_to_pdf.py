"""Convert images to PDF."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger

log = get_logger(__name__)


def image_to_pdf(
    files: list[bytes],
    options: dict[str, any] | None = None,  # type: ignore[type-arg]
    scratch_dir: Path | None = None,
) -> bytes:
    """Convert images to single PDF using Pillow."""
    if not files or len(files) < 1:
        raise ApiError(400, "too_many_files", detail="At least 1 image is required.")

    if len(files) > 20:
        raise ApiError(400, "too_many_files", detail="Maximum 20 images allowed.")

    options = options or {}

    try:
        # Load all images
        pil_images = []
        for img_bytes in files:
            try:
                img = Image.open(io.BytesIO(img_bytes))
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P", "LA"):
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    pil_images.append(rgb_img)
                else:
                    pil_images.append(img.convert("RGB"))
            except Exception as e:
                raise ApiError(
                    400,
                    "unsupported_type",
                    detail="One of the files is not a valid image.",
                ) from e

        # Save as PDF
        output = io.BytesIO()
        pil_images[0].save(output, format="PDF", save_all=True, append_images=pil_images[1:])
        output.seek(0)

        result = output.read()
        log.info("image_to_pdf_success", output_size=len(result), image_count=len(files))
        return result

    except ApiError:
        raise
    except Exception as e:
        log.error("image_to_pdf_failed", error_class=type(e).__name__)
        raise ApiError(500, "processing_failed", detail="Could not convert images to PDF.") from e

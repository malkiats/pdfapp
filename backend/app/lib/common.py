"""Shared helpers for tool implementations: inputs, options, page specs, PDF I/O."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from typing import Any

import pikepdf
from pdfapp.backend.app.core.errors import ApiError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


@dataclass
class ToolInput:
    """Everything a tool receives from one request."""

    files: list[bytes] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    text: str = ""
    urls: list[str] = field(default_factory=list)
    max_pages: int = 100
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"


@dataclass
class ToolResult:
    content: bytes
    media_type: str
    filename: str


def validation_error(pointer: str, message: str) -> ApiError:
    return ApiError(
        400,
        "validation_error",
        detail=message,
        errors=[{"pointer": pointer, "code": "invalid", "message": message}],
    )


# ---------------------------------------------------------------- options


def opt_str(inp: ToolInput, name: str, default: str = "") -> str:
    value = inp.options.get(name, default)
    if value is None:
        return default
    if isinstance(value, list):
        value = ",".join(str(v) for v in value)
    return str(value).strip()


def opt_int(inp: ToolInput, name: str, default: int, lo: int, hi: int) -> int:
    raw = inp.options.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        raise validation_error(f"/options/{name}", f"{name} must be a whole number.") from None
    if not lo <= value <= hi:
        raise validation_error(f"/options/{name}", f"{name} must be between {lo} and {hi}.")
    return value


def opt_float(inp: ToolInput, name: str, default: float, lo: float, hi: float) -> float:
    raw = inp.options.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        raise validation_error(f"/options/{name}", f"{name} must be a number.") from None
    if not lo <= value <= hi:
        raise validation_error(f"/options/{name}", f"{name} must be between {lo:g} and {hi:g}.")
    return value


def opt_choice(inp: ToolInput, name: str, choices: tuple[str, ...], default: str) -> str:
    value = opt_str(inp, name, default).lower() or default
    if value not in choices:
        raise validation_error(f"/options/{name}", f"{name} must be one of: {', '.join(choices)}.")
    return value


def opt_bool(inp: ToolInput, name: str, default: bool) -> bool:
    raw = inp.options.get(name)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------- pages


def parse_pages(spec: str, total: int, pointer: str = "/options/pages") -> list[int]:
    """Parse '1-3,5,8-10' (1-based, 'end' allowed) into 0-based indices, in the given order."""
    pages: list[int] = []
    for raw_part in spec.replace(" ", "").split(","):
        if not raw_part:
            continue
        try:
            if "-" in raw_part:
                start_s, end_s = raw_part.split("-", 1)
                start = int(start_s)
                end = total if end_s.lower() in ("", "end") else int(end_s)
                if start > end:
                    raise ValueError
                pages.extend(range(start, end + 1))
            else:
                pages.append(int(raw_part))
        except ValueError:
            raise validation_error(
                pointer, "Use page numbers and ranges such as 1-3,5,8-10."
            ) from None
    if not pages:
        raise validation_error(pointer, "Enter at least one page number.")
    bad = [p for p in pages if p < 1 or p > total]
    if bad:
        raise validation_error(
            pointer, f"The document has {total} pages; page {bad[0]} does not exist."
        )
    return [p - 1 for p in pages]


# ---------------------------------------------------------------- PDF I/O


def check_page_count(count: int, inp: ToolInput) -> None:
    if count > inp.max_pages:
        raise ApiError(
            422,
            "too_many_pages",
            detail=f"The document has {count} pages; the limit is {inp.max_pages}.",
            params={"limit": inp.max_pages},
        )


def read_pdf(data: bytes, inp: ToolInput) -> PdfReader:
    """Open a PDF with pypdf, mapping failures to API errors."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ApiError(422, "file_encrypted", detail="The PDF is password protected.")
        count = len(reader.pages)
    except ApiError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as e:
        raise ApiError(422, "invalid_file", detail="The file is not a valid PDF.") from e
    if count == 0:
        raise ApiError(422, "invalid_file", detail="The PDF has no pages.")
    check_page_count(count, inp)
    return reader


def open_pikepdf(data: bytes, inp: ToolInput, password: str = "") -> pikepdf.Pdf:
    try:
        pdf = pikepdf.open(io.BytesIO(data), password=password)
    except pikepdf.PasswordError as e:
        raise ApiError(422, "file_encrypted", detail="The PDF is password protected.") from e
    except pikepdf.PdfError as e:
        raise ApiError(422, "invalid_file", detail="The file is not a valid PDF.") from e
    check_page_count(len(pdf.pages), inp)
    return pdf


def writer_bytes(writer: PdfWriter) -> bytes:
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def pikepdf_bytes(pdf: pikepdf.Pdf, **save_kwargs: Any) -> bytes:
    out = io.BytesIO()
    pdf.save(out, **save_kwargs)
    return out.getvalue()


def zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return out.getvalue()


def pdf_result(content: bytes, slug: str) -> ToolResult:
    return ToolResult(content, "application/pdf", f"{slug}-result.pdf")


def text_result(text: str, slug: str, ext: str = "txt") -> ToolResult:
    media = "text/markdown; charset=utf-8" if ext == "md" else "text/plain; charset=utf-8"
    return ToolResult(text.encode("utf-8"), media, f"{slug}-result.{ext}")


def pdf_text(reader: PdfReader) -> str:
    parts = []
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            parts.append(f"[Page {i}]\n{text}")
    return "\n\n".join(parts)

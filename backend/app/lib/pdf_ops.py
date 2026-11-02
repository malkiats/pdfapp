"""PDF tool implementations (organize, optimize, convert, edit, security)."""

from __future__ import annotations

import difflib
import io
import math
import secrets

import pikepdf
import pypdfium2 as pdfium
from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.lib.common import (
    ToolInput,
    ToolResult,
    check_page_count,
    open_pikepdf,
    opt_bool,
    opt_choice,
    opt_float,
    opt_int,
    opt_str,
    parse_pages,
    pdf_result,
    pdf_text,
    pikepdf_bytes,
    read_pdf,
    text_result,
    validation_error,
    writer_bytes,
    zip_bytes,
)
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfWriter
from pypdf.generic import RectangleObject

# ================================================================ organize


def merge_pdf(inp: ToolInput) -> ToolResult:
    writer = PdfWriter()
    total = 0
    for data in inp.files:
        reader = read_pdf(data, inp)
        total += len(reader.pages)
        check_page_count(total, inp)
        writer.append(reader, import_outline=opt_bool(inp, "keep_bookmarks", True))
    return pdf_result(writer_bytes(writer), "merge-pdf")


def split_pdf(inp: ToolInput) -> ToolResult:
    reader = read_pdf(inp.files[0], inp)
    total = len(reader.pages)
    ranges = opt_str(inp, "ranges")
    every_n = inp.options.get("every_n")
    if ranges and every_n not in (None, ""):
        raise validation_error("/options", "Use either page ranges or 'every N pages', not both.")

    groups: list[list[int]] = []
    if ranges:
        # Each comma-separated part becomes one output file.
        for part in ranges.replace(" ", "").split(","):
            if part:
                groups.append(parse_pages(part, total, "/options/ranges"))
    else:
        n = opt_int(inp, "every_n", 1, 1, 10_000)
        groups = [list(range(i, min(i + n, total))) for i in range(0, total, n)]

    entries = []
    for idx, pages in enumerate(groups, 1):
        writer = PdfWriter()
        for p in pages:
            writer.add_page(reader.pages[p])
        entries.append((f"part-{idx:03d}.pdf", writer_bytes(writer)))
    return ToolResult(zip_bytes(entries), "application/zip", "split-pdf-result.zip")


def _select_pages(inp: ToolInput, slug: str, keep_selected: bool) -> ToolResult:
    reader = read_pdf(inp.files[0], inp)
    total = len(reader.pages)
    spec = opt_str(inp, "pages")
    if not spec:
        raise validation_error("/options/pages", "Enter the pages, for example 2,4-6.")
    selected = parse_pages(spec, total)
    if keep_selected:
        keep = selected
    else:
        drop = set(selected)
        keep = [i for i in range(total) if i not in drop]
        if not keep:
            raise validation_error("/options/pages", "You cannot remove every page.")
    writer = PdfWriter()
    for i in keep:
        writer.add_page(reader.pages[i])
    return pdf_result(writer_bytes(writer), slug)


def remove_pages(inp: ToolInput) -> ToolResult:
    return _select_pages(inp, "remove-pages", keep_selected=False)


def extract_pages(inp: ToolInput) -> ToolResult:
    return _select_pages(inp, "extract-pages", keep_selected=True)


def organize_pdf(inp: ToolInput) -> ToolResult:
    reader = read_pdf(inp.files[0], inp)
    spec = opt_str(inp, "page_order")
    if not spec:
        raise validation_error(
            "/options/page_order", "Enter the new page order, for example 3,1,2."
        )
    order = parse_pages(spec, len(reader.pages), "/options/page_order")
    writer = PdfWriter()
    for i in order:
        writer.add_page(reader.pages[i])
    return pdf_result(writer_bytes(writer), "organize-pdf")


# ================================================================ images -> PDF

_PAGE_SIZES = {"a4": (595.0, 842.0), "letter": (612.0, 792.0)}


def images_to_pdf(inp: ToolInput, slug: str) -> ToolResult:
    page_size = opt_choice(inp, "page_size", ("fit", "a4", "letter"), "fit")
    margin = opt_int(inp, "margin", 0, 0, 72) if page_size != "fit" else 0
    if len(inp.files) > inp.max_pages:
        check_page_count(len(inp.files), inp)

    pages: list[Image.Image] = []
    for data in inp.files:
        try:
            img = Image.open(io.BytesIO(data))
            img = ImageOps.exif_transpose(img)
        except (UnidentifiedImageError, OSError) as e:
            raise ApiError(
                422, "invalid_file", detail="One of the images could not be read."
            ) from e
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.getchannel("A"))
            img = background
        else:
            img = img.convert("RGB")

        if page_size != "fit":
            pw, ph = _PAGE_SIZES[page_size]
            if img.width > img.height:
                pw, ph = ph, pw  # landscape page for landscape images
            # Render at 150 dpi on the chosen paper size.
            scale_px = 150 / 72
            canvas = Image.new("RGB", (int(pw * scale_px), int(ph * scale_px)), (255, 255, 255))
            box_w = canvas.width - 2 * int(margin * scale_px)
            box_h = canvas.height - 2 * int(margin * scale_px)
            ratio = min(box_w / img.width, box_h / img.height)
            resized = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))))
            canvas.paste(
                resized,
                ((canvas.width - resized.width) // 2, (canvas.height - resized.height) // 2),
            )
            img = canvas
        pages.append(img)

    out = io.BytesIO()
    pages[0].save(
        out,
        format="PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=150.0 if page_size != "fit" else 96.0,
    )
    return pdf_result(out.getvalue(), slug)


# ================================================================ PDF -> images


def pdf_to_images(inp: ToolInput, fmt: str, slug: str) -> ToolResult:
    read_pdf(inp.files[0], inp)  # validates, counts pages, rejects encrypted files
    dpi = opt_int(inp, "dpi", 110, 50, 300)
    try:
        doc = pdfium.PdfDocument(inp.files[0])
    except pdfium.PdfiumError as e:
        raise ApiError(422, "invalid_file", detail="The file is not a valid PDF.") from e
    try:
        total = len(doc)
        spec = opt_str(inp, "pages")
        indices = parse_pages(spec, total) if spec else list(range(total))
        entries = []
        for i in indices:
            page = doc[i]
            image = page.render(scale=dpi / 72).to_pil()
            buf = io.BytesIO()
            if fmt == "png":
                image.save(buf, format="PNG", optimize=True)
            else:
                image.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
            entries.append((f"page-{i + 1:03d}.{fmt}", buf.getvalue()))
            page.close()
    finally:
        doc.close()
    return ToolResult(zip_bytes(entries), "application/zip", f"{slug}-result.zip")


# ================================================================ optimize


def compress_pdf(inp: ToolInput) -> ToolResult:
    level = opt_choice(inp, "level", ("low", "medium", "high"), "medium")
    original = inp.files[0]
    pdf = open_pikepdf(original, inp)
    settings = {"medium": (1600, 70), "high": (1000, 50)}.get(level)
    if settings:
        max_side, quality = settings
        _recompress_images(pdf, max_side, quality)
    result = pikepdf_bytes(
        pdf,
        compress_streams=True,
        object_stream_mode=pikepdf.ObjectStreamMode.generate,
        recompress_flate=level != "low",
    )
    # Never hand back a bigger file.
    return pdf_result(result if len(result) < len(original) else original, "compress-pdf")


def _recompress_images(pdf: pikepdf.Pdf, max_side: int, quality: int) -> None:
    seen: set[tuple[int, int]] = set()
    for page in pdf.pages:
        for _name, raw in page.images.items():
            key = raw.objgen
            if key in seen:
                continue
            seen.add(key)
            try:
                if (
                    raw.get("/ImageMask")
                    or raw.get("/SMask") is not None
                    or raw.get("/Mask") is not None
                ):
                    continue
                pil = pikepdf.PdfImage(raw).as_pil_image()
                if pil.mode not in ("RGB", "L"):
                    pil = pil.convert("RGB")
                if max(pil.size) > max_side:
                    pil.thumbnail((max_side, max_side))
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=quality, optimize=True)
                data = buf.getvalue()
                if len(data) >= len(raw.read_raw_bytes()):
                    continue
                raw.write(data, filter=pikepdf.Name.DCTDecode)
                raw.Width, raw.Height = pil.size
                raw.ColorSpace = (
                    pikepdf.Name.DeviceGray if pil.mode == "L" else pikepdf.Name.DeviceRGB
                )
                raw.BitsPerComponent = 8
                for key_name in ("/DecodeParms", "/Decode"):
                    if key_name in raw:
                        del raw[key_name]
            except Exception:  # noqa: BLE001, S112 - an image we cannot recompress is left as is
                continue


def repair_pdf(inp: ToolInput) -> ToolResult:
    # qpdf reconstructs broken cross-reference tables while opening.
    pdf = open_pikepdf(inp.files[0], inp)
    return pdf_result(pikepdf_bytes(pdf, fix_metadata_version=True), "repair-pdf")


# ================================================================ edit


def rotate_pdf(inp: ToolInput) -> ToolResult:
    angle = opt_int(inp, "angle", 90, 0, 360)
    if angle not in (90, 180, 270):
        raise validation_error("/options/angle", "Angle must be 90, 180 or 270.")
    reader = read_pdf(inp.files[0], inp)
    spec = opt_str(inp, "pages")
    targets = set(parse_pages(spec, len(reader.pages))) if spec else set(range(len(reader.pages)))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in targets:
            page.rotate(angle)
        writer.add_page(page)
    return pdf_result(writer_bytes(writer), "rotate-pdf")


def crop_pdf(inp: ToolInput) -> ToolResult:
    mm = opt_float(inp, "margin_mm", 10, 0, 200)
    pts = mm * 72 / 25.4
    reader = read_pdf(inp.files[0], inp)
    writer = PdfWriter()
    for page in reader.pages:
        box = page.cropbox
        left, bottom, right, top = (
            float(box.left),
            float(box.bottom),
            float(box.right),
            float(box.top),
        )
        if right - left <= 2 * pts + 36 or top - bottom <= 2 * pts + 36:
            raise validation_error("/options/margin_mm", "The margin is larger than the page.")
        new_box = RectangleObject([left + pts, bottom + pts, right - pts, top - pts])
        page.cropbox = new_box
        page.trimbox = new_box
        writer.add_page(page)
    return pdf_result(writer_bytes(writer), "crop-pdf")


def _pdf_string(text: str) -> str:
    safe = text.encode("cp1252", errors="replace").decode("cp1252")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text_width(text: str, size: float) -> float:
    # Helvetica averages ~0.52 em per character; good enough for placement.
    return len(text) * size * 0.52


def _add_overlay(
    page: pikepdf.Page, pdf: pikepdf.Pdf, stream: bytes, opacity: float | None = None
) -> None:
    font = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font,
            Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica,
            Encoding=pikepdf.Name.WinAnsiEncoding,
        )
    )
    font_name = page.add_resource(font, pikepdf.Name.Font, prefix="DTF")
    gs_cmd = b""
    if opacity is not None:
        gs = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, ca=opacity, CA=opacity)
        )
        gs_name = page.add_resource(gs, pikepdf.Name.ExtGState, prefix="DTG")
        gs_cmd = f"{gs_name} gs ".encode()
    stream = stream.replace(b"/FONT", str(font_name).encode())
    # Isolate the original content's graphics state from ours.
    page.contents_add(pikepdf.Stream(pdf, b"q\n"), prepend=True)
    page.contents_add(pikepdf.Stream(pdf, b"\nQ\nq " + gs_cmd + stream + b" Q\n"))


def add_page_numbers(inp: ToolInput) -> ToolResult:
    position = opt_choice(
        inp,
        "position",
        ("bottom-center", "bottom-right", "bottom-left", "top-center", "top-right", "top-left"),
        "bottom-center",
    )
    style = opt_choice(inp, "format", ("n", "page-n", "page-n-of-total", "n-of-total"), "n")
    start = opt_int(inp, "start", 1, 0, 100_000)
    size = opt_int(inp, "font_size", 11, 6, 48)
    pdf = open_pikepdf(inp.files[0], inp)
    total = len(pdf.pages)
    for idx, page in enumerate(pdf.pages):
        n = start + idx
        label = {
            "n": f"{n}",
            "page-n": f"Page {n}",
            "page-n-of-total": f"Page {n} of {start + total - 1}",
            "n-of-total": f"{n} / {start + total - 1}",
        }[style]
        box = page.trimbox
        x0, y0, x1, y1 = (float(v) for v in box)
        margin = 24
        width = _text_width(label, size)
        vertical, horizontal = position.split("-")
        y = y0 + margin if vertical == "bottom" else y1 - margin - size
        x = {"left": x0 + margin, "center": (x0 + x1 - width) / 2, "right": x1 - margin - width}[
            horizontal
        ]
        stream = f"BT /FONT {size} Tf 0 g 1 0 0 1 {x:.2f} {y:.2f} Tm ({_pdf_string(label)}) Tj ET".encode()
        _add_overlay(page, pdf, stream)
    return pdf_result(pikepdf_bytes(pdf), "add-page-numbers")


def add_watermark(inp: ToolInput) -> ToolResult:
    text = opt_str(inp, "text")
    if not text:
        raise validation_error("/options/text", "Enter the watermark text.")
    if len(text) > 100:
        raise validation_error("/options/text", "Use at most 100 characters.")
    opacity = opt_int(inp, "opacity", 25, 5, 100) / 100
    layout = opt_choice(inp, "layout", ("diagonal", "horizontal"), "diagonal")
    pdf = open_pikepdf(inp.files[0], inp)
    for page in pdf.pages:
        x0, y0, x1, y1 = (float(v) for v in page.trimbox)
        w, h = x1 - x0, y1 - y0
        angle = math.atan2(h, w) if layout == "diagonal" else 0.0
        span = math.hypot(w, h) if layout == "diagonal" else w
        size = max(10.0, min(96.0, span * 0.7 / max(1, len(text) * 0.52)))
        tw = _text_width(text, size)
        cos, sin = math.cos(angle), math.sin(angle)
        cx, cy = x0 + w / 2, y0 + h / 2
        # Start point so the text's centre lands on the page centre.
        sx = cx - (tw / 2) * cos + (size / 3) * sin
        sy = cy - (tw / 2) * sin - (size / 3) * cos
        stream = (
            f"BT /FONT {size:.1f} Tf 0.5 g {cos:.4f} {sin:.4f} {-sin:.4f} {cos:.4f} {sx:.2f} {sy:.2f} Tm "
            f"({_pdf_string(text)}) Tj ET"
        ).encode()
        _add_overlay(page, pdf, stream, opacity=opacity)
    return pdf_result(pikepdf_bytes(pdf), "add-watermark")


# ================================================================ security


def unlock_pdf(inp: ToolInput) -> ToolResult:
    password = opt_str(inp, "password")
    try:
        pdf = pikepdf.open(io.BytesIO(inp.files[0]), password=password)
    except pikepdf.PasswordError as e:
        raise ApiError(422, "wrong_password", detail="The password is not correct.") from e
    except pikepdf.PdfError as e:
        raise ApiError(422, "invalid_file", detail="The file is not a valid PDF.") from e
    check_page_count(len(pdf.pages), inp)
    return pdf_result(pikepdf_bytes(pdf, encryption=False), "unlock-pdf")


def protect_pdf(inp: ToolInput) -> ToolResult:
    password = opt_str(inp, "password")
    if len(password) < 4:
        raise validation_error("/options/password", "Use a password with at least 4 characters.")
    if len(password) > 128:
        raise validation_error("/options/password", "Use at most 128 characters.")
    allow_print = opt_bool(inp, "allow_printing", True)
    allow_copy = opt_bool(inp, "allow_copying", False)
    pdf = open_pikepdf(inp.files[0], inp)
    permissions = pikepdf.Permissions(
        print_lowres=allow_print,
        print_highres=allow_print,
        extract=allow_copy,
        accessibility=True,
        modify_annotation=False,
        modify_assembly=False,
        modify_form=False,
        modify_other=False,
    )
    encryption = pikepdf.Encryption(
        owner=secrets.token_urlsafe(24), user=password, R=6, allow=permissions
    )
    return pdf_result(pikepdf_bytes(pdf, encryption=encryption), "protect-pdf")


def compare_pdf(inp: ToolInput) -> ToolResult:
    a = pdf_text(read_pdf(inp.files[0], inp)).splitlines()
    b = pdf_text(read_pdf(inp.files[1], inp)).splitlines()
    diff = list(difflib.unified_diff(a, b, "first.pdf", "second.pdf", lineterm="", n=2))
    added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
    removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
    if not diff:
        body = "No differences found in the text of the two documents."
    else:
        body = "\n".join(diff)
    report = (
        "PDF text comparison\n"
        f"Lines added: {added}\nLines removed: {removed}\n"
        "Lines starting with '-' exist only in the first PDF, '+' only in the second.\n\n"
        f"{body}\n"
    )
    return text_result(report, "compare-pdf")

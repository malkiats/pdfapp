"""Word, PowerPoint, Excel and HTML to PDF.

Text-and-structure conversions with reportlab: headings, paragraphs, lists and
tables are kept and wrapped to the page; images, fonts and exact layout are not.
Nothing is silently cut: if a limit is hit the PDF ends with a visible note.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Iterator
from html import escape
from html.parser import HTMLParser
from typing import Any

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.lib.common import ToolInput, ToolResult, pdf_result, read_pdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

# Bounds the work per request (and the 60 s function limit).
MAX_BLOCKS = 20_000
MAX_SHEET_ROWS = 5_000
MAX_SHEET_COLS = 30
MAX_CELL_CHARS = 1_000


def _styles() -> StyleSheet1:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle("Note", parent=styles["Italic"], textColor=colors.grey))
    return styles


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    """A Paragraph from plain text (escaped: reportlab parses markup)."""
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _table(rows: list[list[str]], styles: StyleSheet1, width: float) -> LongTable:
    cols = max(len(r) for r in rows)
    cells = [
        [_para(c[:MAX_CELL_CHARS], styles["Cell"]) for c in r + [""] * (cols - len(r))]
        for r in rows
    ]
    table = LongTable(cells, colWidths=[width / cols] * cols, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _build(story: list[Flowable], slug: str, pagesize: tuple[float, float] = A4) -> ToolResult:
    if not story:
        raise ApiError(422, "processing_failed", detail="The document has no text to convert.")
    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=pagesize,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(story)
    return pdf_result(out.getvalue(), slug)


def _capped(blocks: Iterable[Flowable], styles: StyleSheet1) -> list[Flowable]:
    story: list[Flowable] = []
    for i, block in enumerate(blocks):
        if i >= MAX_BLOCKS:
            story.append(
                _para("(The document is very long; the rest was not converted.)", styles["Note"])
            )
            break
        story.append(block)
    return story


def _open(loader: Any, data: bytes, what: str) -> Any:
    try:
        return loader(io.BytesIO(data))
    except Exception as e:
        raise ApiError(422, "invalid_file", detail=f"The file is not a valid {what}.") from e


# ---------------------------------------------------------------- Word


def word_to_pdf(inp: ToolInput) -> ToolResult:
    from docx import Document
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph as DocxParagraph

    document = _open(Document, inp.files[0], "Word document")
    styles = _styles()
    width = A4[0] - 36 * mm

    def blocks() -> Iterator[Flowable]:
        # Body order: paragraphs and tables interleaved as in the document.
        for child in document.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                p = DocxParagraph(child, document)
                text = p.text.strip()
                if not text:
                    continue
                name = (p.style.name if p.style is not None else "") or ""
                if name == "Title":
                    yield _para(text, styles["Title"])
                elif name.startswith("Heading"):
                    level = name.removeprefix("Heading").strip()
                    yield _para(
                        text,
                        styles[f"Heading{level}"]
                        if level in {"1", "2", "3"}
                        else styles["Heading4"],
                    )
                elif "List" in name:
                    yield _para(f"• {text}", styles["BodyText"])
                else:
                    yield _para(text, styles["BodyText"])
            elif tag == "tbl":
                rows = [
                    [cell.text.strip() for cell in row.cells]
                    for row in DocxTable(child, document).rows
                ]
                if rows:
                    yield Spacer(1, 2 * mm)
                    yield _table(rows, styles, width)
                    yield Spacer(1, 4 * mm)

    return _build(_capped(blocks(), styles), "word-to-pdf")


# ---------------------------------------------------------------- PowerPoint


def powerpoint_to_pdf(inp: ToolInput) -> ToolResult:
    from pptx import Presentation

    presentation = _open(Presentation, inp.files[0], "PowerPoint presentation")
    styles = _styles()
    pagesize = landscape(A4)
    width = pagesize[0] - 36 * mm

    def shape_blocks(shape: Any) -> Iterator[Flowable]:
        if getattr(shape, "has_table", False) and shape.has_table:
            rows = [[cell.text.strip() for cell in row.cells] for row in shape.table.rows]
            if rows:
                yield _table(rows, styles, width)
        elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                text = "".join(run.text for run in paragraph.runs).strip()
                if text:
                    yield _para(("    " * paragraph.level) + "• " + text, styles["BodyText"])
        elif shape.shape_type == 6:  # group: walk its children
            for child in shape.shapes:
                yield from shape_blocks(child)

    def blocks() -> Iterator[Flowable]:
        for number, slide in enumerate(presentation.slides, 1):
            if number > 1:
                yield PageBreak()
            title_shape = slide.shapes.title
            # python-pptx returns new proxy objects on each access: compare by shape id.
            title_id = title_shape.shape_id if title_shape is not None else None
            title = (
                title_shape.text.strip()
                if title_shape is not None and title_shape.has_text_frame
                else ""
            )
            yield _para(title or f"Slide {number}", styles["Heading1"])
            # Top-to-bottom, then left-to-right: the order people read a slide.
            shapes = sorted(
                (s for s in slide.shapes if s.shape_id != title_id),
                key=lambda s: ((s.top or 0), (s.left or 0)),
            )
            for shape in shapes:
                yield from shape_blocks(shape)
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    yield Spacer(1, 4 * mm)
                    yield _para(f"Notes: {notes}", styles["Note"])

    return _build(_capped(blocks(), styles), "powerpoint-to-pdf", pagesize)


# ---------------------------------------------------------------- Excel


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def excel_to_pdf(inp: ToolInput) -> ToolResult:
    from openpyxl import load_workbook

    workbook = _open(
        lambda f: load_workbook(f, read_only=True, data_only=True), inp.files[0], "Excel workbook"
    )
    styles = _styles()
    pagesize = landscape(A4)
    width = pagesize[0] - 36 * mm
    story: list[Flowable] = []
    try:
        for sheet in workbook.worksheets:
            rows: list[list[str]] = []
            truncated = False
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                if i >= MAX_SHEET_ROWS:
                    truncated = True
                    break
                cells = [_cell_text(v) for v in row[:MAX_SHEET_COLS]]
                truncated = truncated or len(row) > MAX_SHEET_COLS
                rows.append(cells)
            # Drop trailing empty rows and columns.
            while rows and not any(rows[-1]):
                rows.pop()
            if not rows:
                continue
            last_col = max(max((j for j, c in enumerate(r) if c), default=-1) for r in rows)
            rows = [r[: last_col + 1] for r in rows]
            if story:
                story.append(PageBreak())
            story.append(KeepTogether([_para(sheet.title, styles["Heading2"])]))
            story.append(_table(rows, styles, width))
            if truncated:
                story.append(
                    _para(
                        f"(Only the first {MAX_SHEET_ROWS:,} rows and {MAX_SHEET_COLS} "
                        "columns are shown.)",
                        styles["Note"],
                    )
                )
    finally:
        workbook.close()
    return _build(story, "excel-to-pdf", pagesize)


# ---------------------------------------------------------------- HTML

_BLOCK_STYLES = {
    "h1": "Heading1",
    "h2": "Heading2",
    "h3": "Heading3",
    "h4": "Heading4",
    "h5": "Heading5",
    "h6": "Heading6",
}
_BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "header",
    "footer",
    "li",
    "br",
    "tr",
    "blockquote",
    "pre",
    "table",
    "ul",
    "ol",
} | set(_BLOCK_STYLES)
_SKIP_TAGS = {"script", "style", "head", "noscript", "template", "svg"}


class _HtmlBlocks(HTMLParser):
    """Collects (style, text) blocks from HTML; scripts and styles are ignored."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._text: list[str] = []
        self._style = "BodyText"
        self._skip = 0

    def _flush(self) -> None:
        text = " ".join("".join(self._text).split())
        if text:
            self.blocks.append((self._style, text))
        self._text = []
        self._style = "BodyText"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self._flush()
            if tag in _BLOCK_STYLES:
                self._style = _BLOCK_STYLES[tag]
            elif tag == "li":
                self._text.append("• ")
        elif tag in {"td", "th"}:
            self._text.append(" | " if self._text else "")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._text.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def html_to_pdf(inp: ToolInput) -> ToolResult:
    html = inp.files[0].decode("utf-8", errors="replace")
    parser = _HtmlBlocks()
    parser.feed(html)
    parser.close()
    styles = _styles()
    return _build(
        _capped((_para(text, styles[style]) for style, text in parser.blocks), styles),
        "html-to-pdf",
    )


# ---------------------------------------------------------------- PDF to Word / PowerPoint / Excel

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MEDIA = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_XLSX_ROWS = 50_000


def _pdf_pages(inp: ToolInput) -> Any:
    """Opens the PDF with pdfplumber after the shared checks (valid, not encrypted, page cap)."""
    import pdfplumber

    read_pdf(inp.files[0], inp)
    try:
        return pdfplumber.open(io.BytesIO(inp.files[0]))
    except Exception as e:
        raise ApiError(422, "invalid_file", detail="The file is not a valid PDF.") from e


def _page_lines(page: Any) -> list[str]:
    return [line.strip() for line in (page.extract_text() or "").splitlines() if line.strip()]


def _no_text() -> ApiError:
    return ApiError(
        422,
        "no_text_layer",
        detail="This PDF has no selectable text. Use Scanned document to text first.",
    )


def _saved(doc: Any) -> bytes:
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def pdf_to_word(inp: ToolInput) -> ToolResult:
    """Text in reading order, one Word page per PDF page (layout and images are not kept)."""
    from docx import Document
    from docx.enum.text import WD_BREAK

    document = Document()
    found = False
    with _pdf_pages(inp) as pdf:
        for number, page in enumerate(pdf.pages):
            lines = _page_lines(page)
            if number > 0 and document.paragraphs:
                document.paragraphs[-1].add_run().add_break(WD_BREAK.PAGE)
            for line in lines:
                document.add_paragraph(line)
            found = found or bool(lines)
            page.close()
    if not found:
        raise _no_text()
    return ToolResult(_saved(document), DOCX_MEDIA, "pdf-to-word-result.docx")


def pdf_to_powerpoint(inp: ToolInput) -> ToolResult:
    """One slide per PDF page: first line as the title, the rest as editable text."""
    from pptx import Presentation
    from pptx.util import Pt

    presentation = Presentation()
    found = False
    with _pdf_pages(inp) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            lines = _page_lines(page)
            page.close()
            found = found or bool(lines)
            slide = presentation.slides.add_slide(presentation.slide_layouts[1])
            slide.shapes.title.text = lines[0][:200] if lines else f"Page {number}"
            frame = slide.placeholders[1].text_frame
            frame.word_wrap = True
            body = lines[1:]
            size = Pt(18 if len(body) <= 8 else 14 if len(body) <= 16 else 10)
            for i, line in enumerate(body):
                paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
                paragraph.text = line
                paragraph.font.size = size
    if not found:
        raise _no_text()
    return ToolResult(_saved(presentation), PPTX_MEDIA, "pdf-to-powerpoint-result.pptx")


def pdf_to_excel(inp: ToolInput) -> ToolResult:
    """Tables found on each page, one sheet per page; pages without tables give their text lines."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    workbook.remove(workbook.active)
    rows_written = 0
    found = False
    with _pdf_pages(inp) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            tables = [
                t for t in page.extract_tables() if t and any(any(c for c in row) for row in t)
            ]
            lines = [] if tables else _page_lines(page)
            page.close()
            if not tables and not lines:
                continue
            found = True
            sheet = workbook.create_sheet(f"Page {number}")
            if tables:
                for t_index, table in enumerate(tables):
                    if t_index:
                        sheet.append([])
                    for r_index, row in enumerate(table):
                        if rows_written >= MAX_XLSX_ROWS:
                            break
                        sheet.append([(c or "").strip() for c in row])
                        if r_index == 0:
                            for cell in sheet[sheet.max_row]:
                                cell.font = Font(bold=True)
                        rows_written += 1
            else:
                for line in lines:
                    if rows_written >= MAX_XLSX_ROWS:
                        break
                    sheet.append([line])
                    rows_written += 1
            if rows_written >= MAX_XLSX_ROWS:
                sheet.append([f"(Stopped after {MAX_XLSX_ROWS:,} rows.)"])
                break
    if not found:
        raise _no_text()
    return ToolResult(_saved(workbook), XLSX_MEDIA, "pdf-to-excel-result.xlsx")

"""Office/HTML to PDF conversions, file-type sniffing and image to text (Groq faked)."""

from __future__ import annotations

import io
import json
from typing import Any

import httpx
import pytest
from docx import Document
from openpyxl import Workbook
from pdfapp.backend.app.api.tool_runner import accepted, sniff_mime
from pdfapp.backend.app.lib import ai
from PIL import Image
from pptx import Presentation
from pypdf import PdfReader

ORIGIN = {"Origin": "https://pdfapp-frontend.vercel.app"}
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def make_docx() -> bytes:
    doc = Document()
    doc.add_heading("Quarterly report", 1)
    doc.add_paragraph("A long paragraph " * 30 + "END-OF-PARAGRAPH & <markup>")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Name", "Total"
    table.cell(1, 0).text, table.cell(1, 1).text = "Widgets", "42"
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def make_pptx() -> bytes:
    prs = Presentation()
    for n in (1, 2):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = f"Slide title {n}"
        slide.placeholders[1].text = f"First bullet {n}\nSecond bullet {n}"
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def make_xlsx(rows: int = 60) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "Total"])
    for i in range(rows):
        ws.append([f"Row {i + 1}", i])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


HTML = (
    b"<!DOCTYPE html><html><head><style>p{}</style><script>alert(1)</script></head>"
    b"<body><h1>Hello</h1><p>Tom &amp; Jerry &lt;3</p><ul><li>One</li></ul></body></html>"
)


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (300, 100), "white").save(out, "PNG")
    return out.getvalue()


def pdf_text(content: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)


async def post(
    client: httpx.AsyncClient, slug: str, data: bytes, name: str, **fields: str
) -> httpx.Response:
    return await client.post(
        f"/api/v1/{slug}",
        files=[("files", (name, data))],
        data={"options": json.dumps({}), **fields},
        headers=ORIGIN,
    )


@pytest.mark.parametrize(
    ("data", "mime"),
    [
        (make_docx(), DOCX),
        (make_pptx(), PPTX),
        (make_xlsx(), XLSX),
        (HTML, "text/html"),
        (b"  \n<html><body>x</body></html>", "text/html"),
        (b"plain words", "text/plain"),
        (b"PK\x03\x04not really a zip", "application/octet-stream"),
    ],
)
def test_sniff_mime(data: bytes, mime: str) -> None:
    assert sniff_mime(data) == mime


def test_html_is_still_accepted_where_plain_text_is() -> None:
    assert accepted("text/html", ["text/plain"])
    assert not accepted("text/html", ["application/pdf"])


async def test_word_to_pdf_keeps_all_text(client: httpx.AsyncClient) -> None:
    response = await post(client, "word-to-pdf", make_docx(), "report.docx")
    assert response.status_code == 200, response.text
    text = pdf_text(response.content)
    assert "Quarterly report" in text
    assert "END-OF-PARAGRAPH & <markup>" in text.replace("\n", " ")  # wrapped, not cut at 100 chars
    assert "Widgets" in text
    assert "42" in text


async def test_powerpoint_to_pdf_one_page_per_slide(client: httpx.AsyncClient) -> None:
    response = await post(client, "powerpoint-to-pdf", make_pptx(), "deck.pptx")
    assert response.status_code == 200, response.text
    pages = [p.extract_text() or "" for p in PdfReader(io.BytesIO(response.content)).pages]
    assert len(pages) == 2
    assert "Slide title 2" in pages[1]
    assert "Second bullet 2" in pages[1]


async def test_excel_to_pdf_keeps_every_row(client: httpx.AsyncClient) -> None:
    response = await post(client, "excel-to-pdf", make_xlsx(60), "book.xlsx")
    assert response.status_code == 200, response.text
    text = pdf_text(response.content)
    assert "Row 1" in text
    assert "Row 60" in text  # the old version stopped after 20 rows


async def test_html_to_pdf_escapes_markup_and_skips_scripts(client: httpx.AsyncClient) -> None:
    response = await post(client, "html-to-pdf", HTML, "page.html")
    assert response.status_code == 200, response.text
    text = pdf_text(response.content)
    assert "Hello" in text
    assert "Tom & Jerry <3" in text
    assert "alert" not in text


async def test_broken_office_file_is_invalid(client: httpx.AsyncClient) -> None:
    broken = make_docx()[:400]
    response = await post(client, "word-to-pdf", broken, "x.docx")
    assert response.status_code in (400, 422)


async def test_image_to_text_needs_consent_and_key(client: httpx.AsyncClient) -> None:
    no_consent = await post(client, "image-to-text", png(), "a.png")
    assert no_consent.status_code == 400
    no_key = await post(client, "image-to-text", png(), "a.png", ai_consent="true")
    assert no_key.status_code == 503
    assert no_key.json()["code"] == "ai_unavailable"


def test_image_is_read_by_the_vision_model(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, Any]] = []

    def chat(
        inp: Any, model: str, messages: list[dict[str, Any]], max_tokens: int, **_: Any
    ) -> str:
        seen.append({"model": model, "messages": messages})
        return "Coffee 3.50\nTotal 3.50"

    monkeypatch.setattr(ai, "_chat", chat)
    inp = ai.ToolInput(files=[png()], groq_api_key="k", groq_vision_model="vision")
    result = ai.receipt_to_text(inp)
    assert result.content.decode() == "Coffee 3.50\nTotal 3.50"
    assert result.filename == "receipt-to-text-result.txt"
    prompt = seen[0]["messages"][0]["content"]
    assert "receipt" in prompt[0]["text"]
    assert prompt[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def table_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    out = io.BytesIO()
    table = Table([["Item", "Qty"], ["Apples", "3"], ["Pears", "5"]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, "black")]))
    SimpleDocTemplate(out, pagesize=A4).build([table])
    return out.getvalue()


async def test_pdf_to_excel_extracts_tables(client: httpx.AsyncClient) -> None:
    from openpyxl import load_workbook

    response = await post(client, "pdf-to-excel", table_pdf(), "t.pdf")
    assert response.status_code == 200, response.text
    sheet = load_workbook(io.BytesIO(response.content)).worksheets[0]
    rows = [[c.value for c in row] for row in sheet.iter_rows()]
    assert rows[:3] == [["Item", "Qty"], ["Apples", "3"], ["Pears", "5"]]


async def test_pdf_to_word_and_powerpoint_keep_page_text(client: httpx.AsyncClient) -> None:
    word = await post(client, "pdf-to-word", table_pdf(), "t.pdf")
    assert word.status_code == 200, word.text
    assert "Apples" in "\n".join(p.text for p in Document(io.BytesIO(word.content)).paragraphs)
    assert "[Page" not in "\n".join(p.text for p in Document(io.BytesIO(word.content)).paragraphs)
    deck = await post(client, "pdf-to-powerpoint", table_pdf(), "t.pdf")
    assert deck.status_code == 200, deck.text
    assert len(Presentation(io.BytesIO(deck.content)).slides) == 1  # one slide per page


async def test_pdf_to_word_on_a_scan_says_so(client: httpx.AsyncClient) -> None:
    import pikepdf

    blank = pikepdf.new()
    blank.add_blank_page()
    out = io.BytesIO()
    blank.save(out)
    response = await post(client, "pdf-to-word", out.getvalue(), "scan.pdf")
    assert response.status_code == 422
    assert response.json()["code"] == "no_text_layer"

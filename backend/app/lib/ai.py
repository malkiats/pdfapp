"""AI document tools backed by the Groq chat-completions API (only with user consent)."""

from __future__ import annotations

import base64
import io
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pypdfium2 as pdfium
from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.lib.common import (
    ToolInput,
    ToolResult,
    opt_choice,
    opt_str,
    pdf_text,
    read_pdf,
    text_result,
    validation_error,
)
from pdfapp.backend.app.lib.web import fetch_page, html_to_text

log = get_logger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Keeps requests inside Groq's per-minute token limits on the free tier.
_MAX_INPUT_CHARS = 24_000
_TIMEOUT = 60
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
# Scanned PDFs: pages read by the vision model. Kept small so that reading the
# pages (in parallel) plus the answer fit inside Vercel's 60 s function limit.
_OCR_MAX_PAGES = 8
_OCR_WORKERS = 4
_OCR_MAX_SIDE = 1600
_OCR_TIMEOUT = 25


def _require_key(inp: ToolInput) -> str:
    if not inp.groq_api_key:
        raise ApiError(503, "ai_unavailable", detail="AI tools are not configured on this server.")
    return inp.groq_api_key


def _complete(inp: ToolInput, system: str, user: str, max_tokens: int = 1500) -> str:
    return _chat(
        inp,
        inp.groq_model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens,
    )


def _chat(
    inp: ToolInput,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    timeout: float = _TIMEOUT,
) -> str:
    api_key = _require_key(inp)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        _GROQ_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "doc-tools/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        log.warning("ai_provider_error", status=e.code)
        if e.code == 429:
            raise ApiError(
                429, "rate_limited", detail="The AI provider is busy.", retry_after_seconds=30
            ) from e
        raise ApiError(502, "ai_unavailable", detail="The AI provider returned an error.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(
            504, "processing_timeout", detail="The AI provider did not respond in time."
        ) from e
    try:
        content = str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as e:
        raise ApiError(
            502, "ai_unavailable", detail="The AI provider returned an empty answer."
        ) from e
    # Reasoning models may prefix their answer with a <think> block.
    return _THINK_RE.sub("", content).strip()


def _page_images(data: bytes) -> tuple[list[bytes], bool]:
    """Renders the first pages of a PDF as JPEGs for the vision model."""
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        raise ApiError(422, "invalid_file", detail="The PDF is not valid.") from e
    try:
        total = len(doc)
        images = []
        for i in range(min(total, _OCR_MAX_PAGES)):
            width, height = doc.get_page_size(i)
            # Fit the longest side to _OCR_MAX_SIDE px: readable text, small upload.
            scale = min(_OCR_MAX_SIDE / max(width, height, 1), 200 / 72)
            page = doc[i]
            image = page.render(scale=scale).to_pil().convert("RGB")
            page.close()
            buf = io.BytesIO()
            image.save(buf, "JPEG", quality=80)
            images.append(buf.getvalue())
        return images, total > _OCR_MAX_PAGES
    finally:
        doc.close()


def _read_page(inp: ToolInput, image: bytes) -> str:
    url = "data:image/jpeg;base64," + base64.b64encode(image).decode()
    text = _chat(
        inp,
        inp.groq_vision_model,
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribe all text on this page exactly, in reading order. "
                        "Keep headings, lists and table rows on their own lines. Output only "
                        "the text. If the page has no text, output nothing.",
                    },
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            }
        ],
        max_tokens=4000,
        timeout=_OCR_TIMEOUT,
    )
    return text


def _ocr_text(inp: ToolInput, data: bytes) -> str:
    """Reads a scanned PDF with the vision model (the user has consented to sending it)."""
    _require_key(inp)  # fail fast, before rendering anything
    images, cut = _page_images(data)
    with ThreadPoolExecutor(max_workers=_OCR_WORKERS) as pool:
        pages = list(pool.map(lambda img: _read_page(inp, img), images))
    log.info("ai_ocr", pages=len(images))
    text = "\n\n".join(f"[Page {i}]\n{t}" for i, t in enumerate(pages, 1) if t.strip())
    if text and cut:
        text += f"\n\n(Only the first {_OCR_MAX_PAGES} pages of this scanned document were read.)"
    return text


def _clip(text: str) -> tuple[str, bool]:
    text = text.strip()
    return (text[:_MAX_INPUT_CHARS], len(text) > _MAX_INPUT_CHARS)


def _document_text(inp: ToolInput) -> str:
    """Text from the uploaded PDF / text file, or from the text field."""
    if inp.files:
        data = inp.files[0]
        if data.startswith(b"%PDF"):
            text = pdf_text(read_pdf(data, inp))
            if not text.strip():
                # A scan: no text layer, so read the page images instead.
                text = _ocr_text(inp, data)
            if not text.strip():
                raise ApiError(
                    422,
                    "no_text_layer",
                    detail="No readable text was found in this PDF.",
                )
            return text
        return data.decode("utf-8", errors="replace")
    if inp.text.strip():
        return inp.text
    raise validation_error("/text", "Provide a document or some text.")


def _note(truncated: bool) -> str:
    return (
        "\n\n(Note: the document was long, so only its first part was used.)" if truncated else ""
    )


def _summarize(inp: ToolInput, text: str, slug: str) -> ToolResult:
    length = opt_choice(inp, "length", ("short", "medium", "long"), "medium")
    words = {"short": "about 80 words", "medium": "about 200 words", "long": "about 450 words"}[
        length
    ]
    body, cut = _clip(text)
    answer = _complete(
        inp,
        "You summarize documents faithfully. Use only information in the document. "
        "Reply in the document's language unless asked otherwise.",
        f"Summarize the following document in {words}. Start with a one-sentence overview, "
        f"then the key points as bullet points.\n\n---\n{body}",
    )
    return text_result(answer + _note(cut), slug)


def summarize_pdf(inp: ToolInput) -> ToolResult:
    return _summarize(inp, _document_text(inp), "summarize-pdf")


def summarize_article(inp: ToolInput) -> ToolResult:
    if inp.urls:
        text = html_to_text(fetch_page(inp.urls[0], "/url_a"))
    else:
        text = inp.text
    if not text.strip():
        raise validation_error("/text", "Provide an article link or paste the article text.")
    return _summarize(inp, text, "summarize-article")


def _translate(inp: ToolInput, text: str, slug: str) -> ToolResult:
    language = opt_str(inp, "target_language")
    if not language:
        raise validation_error("/options/target_language", "Choose the language to translate into.")
    if len(language) > 40:
        raise validation_error("/options/target_language", "Language name is too long.")
    body, cut = _clip(text)
    answer = _complete(
        inp,
        "You are a professional translator. Translate faithfully, keep the structure and "
        "line breaks, and output only the translation.",
        f"Translate into {language}:\n\n{body}",
        max_tokens=6000,
    )
    return text_result(answer + _note(cut), slug)


def translate_pdf(inp: ToolInput) -> ToolResult:
    return _translate(inp, _document_text(inp), "translate-pdf")


def translate_text(inp: ToolInput) -> ToolResult:
    if not inp.text.strip():
        raise validation_error("/text", "Enter the text to translate.")
    return _translate(inp, inp.text, "translate-text")


def pdf_to_markdown(inp: ToolInput) -> ToolResult:
    body, cut = _clip(_document_text(inp))
    answer = _complete(
        inp,
        "You convert extracted PDF text into clean, well-structured Markdown. Keep all content, "
        "restore headings, lists and tables, remove page headers/footers and '[Page n]' markers. "
        "Output only Markdown.",
        body,
        max_tokens=6000,
    )
    return text_result(answer + _note(cut), "pdf-to-markdown", ext="md")


def extract_key_points(inp: ToolInput) -> ToolResult:
    body, cut = _clip(_document_text(inp))
    answer = _complete(
        inp,
        "You extract information faithfully from documents. Use only what the document says.",
        "List the key points of this document as bullet points, then a section 'Action items' "
        "with any tasks, deadlines or decisions (write 'None' if there are none).\n\n---\n" + body,
    )
    return text_result(answer + _note(cut), "extract-key-points")


def ask_pdf(inp: ToolInput) -> ToolResult:
    question = opt_str(inp, "question")
    if not question:
        raise validation_error("/options/question", "Enter your question.")
    if len(question) > 1000:
        raise validation_error("/options/question", "Use at most 1000 characters.")
    body, cut = _clip(_document_text(inp))
    answer = _complete(
        inp,
        "Answer questions using only the provided document. If the answer is not in the "
        "document, say so. Cite page numbers like (p. 3) when possible.",
        f"Document:\n---\n{body}\n---\n\nQuestion: {question}",
    )
    return text_result(f"Question: {question}\n\nAnswer:\n{answer}{_note(cut)}", "ask-pdf")

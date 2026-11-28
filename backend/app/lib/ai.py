"""AI document tools backed by the Groq chat-completions API (only with user consent)."""

from __future__ import annotations

import base64
import io
import json
import re
import time
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
from PIL import Image, ImageOps

log = get_logger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq's free tier allows 8,000 tokens per minute per model, counting the input
# plus the max_tokens we reserve. The input cap (settings.groq_max_input_chars,
# ~4 characters per token) defaults to leave room for the longest answer (4k).
_MAX_ANSWER_TOKENS = 4000
# One retry when Groq asks us to wait briefly (Retry-After); longer waits fail fast.
_MAX_RETRY_WAIT = 10.0
_TIMEOUT = 60
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
# Scanned PDFs: each page image costs ~1,800 input tokens plus the reserved answer.
# The page cap is settings.groq_ocr_max_pages; two at a time, within Vercel's 60 s.
_OCR_WORKERS = 2
_OCR_PAGE_TOKENS = 1200
_OCR_MAX_SIDE = 1600
_OCR_TIMEOUT = 25


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    try:
        return float(e.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        return None


def _send(request: urllib.request.Request, timeout: float) -> Any:
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
                return json.load(resp)
        except urllib.error.HTTPError as e:
            log.warning("ai_provider_error", status=e.code)
            if e.code == 429:
                wait = _retry_after(e)
                if attempt == 1 and wait is not None and wait <= _MAX_RETRY_WAIT:
                    time.sleep(wait + 0.5)
                    continue
                raise ApiError(
                    429,
                    "rate_limited",
                    detail="The AI provider is busy.",
                    retry_after_seconds=max(5, int(wait or 30)),
                ) from e
            if e.code == 413:
                raise ApiError(
                    413, "file_too_large", detail="This document is too long for the AI tools."
                ) from e
            raise ApiError(
                502, "ai_unavailable", detail="The AI provider returned an error."
            ) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ApiError(
                504, "processing_timeout", detail="The AI provider did not respond in time."
            ) from e
    raise AssertionError("unreachable")


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
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    if model.startswith("openai/gpt-oss"):
        # Reasoning tokens count against max_tokens and the per-minute limit.
        payload["reasoning_effort"] = "low"
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
    data = _send(request, timeout)
    try:
        content = str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as e:
        raise ApiError(
            502, "ai_unavailable", detail="The AI provider returned an empty answer."
        ) from e
    # Reasoning models may prefix their answer with a <think> block.
    return _THINK_RE.sub("", content).strip()


def _page_images(data: bytes, max_pages: int) -> tuple[list[bytes], bool]:
    """Renders the first pages of a PDF as JPEGs for the vision model."""
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        raise ApiError(422, "invalid_file", detail="The PDF is not valid.") from e
    try:
        total = len(doc)
        images = []
        for i in range(min(total, max_pages)):
            width, height = doc.get_page_size(i)
            # Fit the longest side to _OCR_MAX_SIDE px: readable text, small upload.
            scale = min(_OCR_MAX_SIDE / max(width, height, 1), 200 / 72)
            page = doc[i]
            image = page.render(scale=scale).to_pil().convert("RGB")
            page.close()
            buf = io.BytesIO()
            image.save(buf, "JPEG", quality=80)
            images.append(buf.getvalue())
        return images, total > max_pages
    finally:
        doc.close()


def _read_page(inp: ToolInput, image: bytes, hint: str = "") -> str:
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
                        "the text. If the page has no text, output nothing." + hint,
                    },
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            }
        ],
        max_tokens=_OCR_PAGE_TOKENS,
        timeout=_OCR_TIMEOUT,
    )
    return text


def _ocr_text(inp: ToolInput, data: bytes, hint: str = "") -> str:
    """Reads a scanned PDF with the vision model (the user has consented to sending it)."""
    _require_key(inp)  # fail fast, before rendering anything
    images, cut = _page_images(data, inp.groq_ocr_max_pages)
    with ThreadPoolExecutor(max_workers=_OCR_WORKERS) as pool:
        pages = list(pool.map(lambda img: _read_page(inp, img, hint), images))
    log.info("ai_ocr", pages=len(images))
    text = "\n\n".join(f"[Page {i}]\n{t}" for i, t in enumerate(pages, 1) if t.strip())
    if text and cut:
        pages_read = inp.groq_ocr_max_pages
        text += f"\n\n(Only the first {pages_read} pages of this scanned document were read.)"
    return text


def _clip(inp: ToolInput, text: str) -> tuple[str, bool]:
    text = text.strip()
    limit = inp.groq_max_input_chars
    return (text[:limit], len(text) > limit)


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
    body, cut = _clip(inp, text)
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
    body, cut = _clip(inp, text)
    answer = _complete(
        inp,
        "You are a professional translator. Translate faithfully, keep the structure and "
        "line breaks, and output only the translation.",
        f"Translate into {language}:\n\n{body}",
        max_tokens=_MAX_ANSWER_TOKENS,
    )
    return text_result(answer + _note(cut), slug)


def translate_pdf(inp: ToolInput) -> ToolResult:
    return _translate(inp, _document_text(inp), "translate-pdf")


def translate_text(inp: ToolInput) -> ToolResult:
    if not inp.text.strip():
        raise validation_error("/text", "Enter the text to translate.")
    return _translate(inp, inp.text, "translate-text")


def pdf_to_markdown(inp: ToolInput) -> ToolResult:
    body, cut = _clip(inp, _document_text(inp))
    answer = _complete(
        inp,
        "You convert extracted PDF text into clean, well-structured Markdown. Keep all content, "
        "restore headings, lists and tables, remove page headers/footers and '[Page n]' markers. "
        "Output only Markdown.",
        body,
        max_tokens=_MAX_ANSWER_TOKENS,
    )
    return text_result(answer + _note(cut), "pdf-to-markdown", ext="md")


def extract_key_points(inp: ToolInput) -> ToolResult:
    body, cut = _clip(inp, _document_text(inp))
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
    body, cut = _clip(inp, _document_text(inp))
    answer = _complete(
        inp,
        "Answer questions using only the provided document. If the answer is not in the "
        "document, say so. Cite page numbers like (p. 3) when possible.",
        f"Document:\n---\n{body}\n---\n\nQuestion: {question}",
    )
    return text_result(f"Question: {question}\n\nAnswer:\n{answer}{_note(cut)}", "ask-pdf")


# ------------------------------------------------ Image to text (AI text recognition)

# Above this, an image is rejected before decoding (decompression bombs).
_MAX_IMAGE_PIXELS = 60_000_000


def _image_jpeg(data: bytes) -> bytes:
    """Any accepted image (JPEG, PNG, WebP, TIFF) as an upright JPEG sized for the vision model."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            width, height = probe.size
        if width * height > _MAX_IMAGE_PIXELS:
            raise ApiError(422, "processing_failed", detail="The image is too large to read.")
        with Image.open(io.BytesIO(data)) as img:
            image = ImageOps.exif_transpose(img).convert("RGB")
    except ApiError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as e:
        raise ApiError(422, "invalid_file", detail="The image could not be read.") from e
    image.thumbnail((_OCR_MAX_SIDE + 400, _OCR_MAX_SIDE + 400))
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _recognise(inp: ToolInput, slug: str, hint: str = "") -> ToolResult:
    data = inp.files[0]
    if data.startswith(b"%PDF"):
        text = pdf_text(read_pdf(data, inp))  # a PDF with a text layer needs no recognition
        if not text.strip():
            text = _ocr_text(inp, data, hint)
    else:
        _require_key(inp)
        text = _read_page(inp, _image_jpeg(data), hint)
    if not text.strip():
        raise ApiError(422, "no_text_layer", detail="No readable text was found in this file.")
    return text_result(text, slug)


def image_to_text(inp: ToolInput) -> ToolResult:
    return _recognise(inp, "image-to-text")


def jpg_to_text(inp: ToolInput) -> ToolResult:
    return _recognise(inp, "jpg-to-text")


def png_to_text(inp: ToolInput) -> ToolResult:
    return _recognise(inp, "png-to-text")


def screenshot_to_text(inp: ToolInput) -> ToolResult:
    return _recognise(inp, "screenshot-to-text", " Ignore window controls, icons and buttons.")


def scanned_document_to_text(inp: ToolInput) -> ToolResult:
    return _recognise(inp, "scanned-document-to-text")


def receipt_to_text(inp: ToolInput) -> ToolResult:
    return _recognise(
        inp,
        "receipt-to-text",
        " This is a receipt or invoice: keep each item with its amount on one line.",
    )


def handwriting_to_text(inp: ToolInput) -> ToolResult:
    return _recognise(
        inp,
        "handwriting-to-text",
        " The text is handwritten. Write [illegible] for words you cannot read.",
    )

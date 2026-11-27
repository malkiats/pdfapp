"""AI tools on scanned PDFs: page images are read by the vision model (Groq is faked)."""

from __future__ import annotations

import io
from typing import Any

import pikepdf
import pytest
from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.lib import ai
from pdfapp.backend.app.lib.common import ToolInput


def textless_pdf(pages: int) -> bytes:
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(595, 842))
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def tool_input(data: bytes) -> ToolInput:
    return ToolInput(files=[data], groq_api_key="test-key", groq_vision_model="vision-model")


def fake_chat(answers: dict[str, str], calls: list[dict[str, Any]]) -> Any:
    def chat(
        inp: ToolInput, model: str, messages: list[dict[str, Any]], max_tokens: int, **_: Any
    ) -> str:
        calls.append({"model": model, "messages": messages})
        return answers[model]

    return chat


def test_scanned_pdf_is_read_by_the_vision_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    answers = {"vision-model": "Invoice 42\nTotal: 10 EUR", "openai/gpt-oss-120b": "Summary"}
    monkeypatch.setattr(ai, "_chat", fake_chat(answers, calls))

    result = ai.summarize_pdf(tool_input(textless_pdf(2)))

    assert result.content.decode().startswith("Summary")
    vision = [c for c in calls if c["model"] == "vision-model"]
    assert len(vision) == 2  # one request per page
    image_part = vision[0]["messages"][0]["content"][1]
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    summary_prompt = calls[-1]["messages"][1]["content"]
    assert "[Page 1]\nInvoice 42" in summary_prompt
    assert "[Page 2]\nInvoice 42" in summary_prompt


def test_only_the_first_pages_of_a_long_scan_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    answers = {"vision-model": "Text", "openai/gpt-oss-120b": "Summary"}
    monkeypatch.setattr(ai, "_chat", fake_chat(answers, calls))

    ai.summarize_pdf(tool_input(textless_pdf(ai._OCR_MAX_PAGES + 3)))

    assert sum(c["model"] == "vision-model" for c in calls) == ai._OCR_MAX_PAGES
    assert "Only the first" in calls[-1]["messages"][1]["content"]


def test_scan_with_no_readable_text_reports_no_text_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(ai, "_chat", fake_chat({"vision-model": "  "}, calls))

    with pytest.raises(ApiError) as err:
        ai.summarize_pdf(tool_input(textless_pdf(1)))

    assert err.value.code == "no_text_layer"
    assert err.value.status == 422


def test_reasoning_blocks_are_stripped() -> None:
    assert ai._THINK_RE.sub("", "<think>\nhmm\n</think>\nAnswer").strip() == "Answer"

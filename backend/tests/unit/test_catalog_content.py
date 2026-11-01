"""Content rules for shared/tool-catalog.json beyond the JSON Schema."""

from __future__ import annotations

import json
from typing import Any

import pytest
import yaml

from pdfapp.backend.app.core.catalog import etag_matches, load_catalog, validate_catalog_document
from pdfapp.backend.tests.conftest import CATALOG_PATH, CATALOG_SCHEMA_PATH, OPENAPI_PATH

CATALOG: dict[str, Any] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
TOOLS: list[dict[str, Any]] = CATALOG["tools"]
SPEC = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))

EXPECTED_SLUGS = {
    "organize": [
        "merge-pdf", "split-pdf", "remove-pages", "extract-pages", "organize-pdf", "scan-to-pdf",
    ],
    "optimize": ["compress-pdf", "repair-pdf", "ocr-pdf"],
    "convert-to-pdf": [
        "jpg-to-pdf", "png-to-pdf", "word-to-pdf", "powerpoint-to-pdf", "excel-to-pdf",
        "html-to-pdf",
    ],
    "convert-from-pdf": [
        "pdf-to-jpg", "pdf-to-png", "pdf-to-word", "pdf-to-powerpoint", "pdf-to-excel",
        "pdf-to-pdfa",
    ],
    "edit": [
        "rotate-pdf", "add-page-numbers", "add-watermark", "crop-pdf", "edit-pdf", "pdf-forms",
    ],
    "security": ["unlock-pdf", "protect-pdf", "sign-pdf", "redact-pdf", "compare-pdf"],
    "ocr": [
        "image-to-text", "jpg-to-text", "png-to-text", "screenshot-to-text",
        "scanned-document-to-text", "receipt-to-text", "handwriting-to-text",
    ],
    "ai": [
        "summarize-pdf", "summarize-article", "translate-pdf", "translate-text",
        "pdf-to-markdown", "extract-key-points", "ask-pdf",
    ],
    "compare": ["compare-webpages"],
}  # fmt: skip

FORBIDDEN_CLAIMS = ["zero retention", "never touches", "instantly deleted", "no one can ever"]


def test_catalog_is_valid_and_loads() -> None:
    schema = json.loads(CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert validate_catalog_document(CATALOG, schema) == []
    assert len(load_catalog(CATALOG_PATH, CATALOG_SCHEMA_PATH)) == len(TOOLS)


def test_every_product_tool_is_listed_in_its_category() -> None:
    by_category: dict[str, list[str]] = {}
    for tool in TOOLS:
        by_category.setdefault(tool["category"], []).append(tool["slug"])
    assert by_category == EXPECTED_SLUGS


def test_phase_one_everything_coming_soon() -> None:
    assert {t["status"] for t in TOOLS} == {"coming_soon"}
    assert all(t["phase"] >= 2 for t in TOOLS)


def test_options_schema_names_exist_in_contract() -> None:
    schemas = SPEC["components"]["schemas"]
    for tool in TOOLS:
        if tool["options_schema"] is not None:
            assert tool["options_schema"] in schemas, tool["slug"]


@pytest.mark.parametrize("tool", TOOLS, ids=[t["slug"] for t in TOOLS])
def test_privacy_wording_is_honest(tool: dict[str, Any]) -> None:
    text = json.dumps(tool).lower()
    for claim in FORBIDDEN_CLAIMS:
        assert claim not in text
    faq_text = " ".join(f["answer"] for f in tool["seo"].get("faq", [])).lower()
    assert "deleted" in faq_text
    if tool["category"] == "ai":
        assert tool["requires_ai_consent"] is True
        assert "ai provider" in faq_text
        assert "consent" in faq_text
    else:
        assert tool["requires_ai_consent"] is False


def test_pdfa_marked_pending_licensing() -> None:
    pdfa = next(t for t in TOOLS if t["slug"] == "pdf-to-pdfa")
    assert "licensing" in json.dumps(pdfa).lower()


def test_etag_matching_rules() -> None:
    assert etag_matches('"a"', '"a"')
    assert etag_matches('W/"a"', '"a"')
    assert etag_matches('"b", "a"', '"a"')
    assert etag_matches("*", '"a"')
    assert not etag_matches('"b"', '"a"')
    assert not etag_matches(None, '"a"')

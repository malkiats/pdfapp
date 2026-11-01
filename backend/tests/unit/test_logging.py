from __future__ import annotations

import json
import logging

import pytest

from pdfapp.backend.app.core.logging import (
    ALLOWED_KEYS,
    FORBIDDEN_KEYS,
    configure_logging,
    get_logger,
    redact_mapping,
)

CANARIES = [
    "CANARY-filename-tax-return-2026.pdf",
    "CANARY-content-%PDF-1.7-secret",
    "CANARY-ocr-text-account-balance",
    "https://canary.example.com/private?token=CANARY-query",
    "Bearer CANARY-jwt",
    "anon_sid=CANARY-cookie",
    "/data/workspaces/CANARY-path",
]


def _lines(captured: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in captured.splitlines() if line.strip()]


def test_allowlist_and_forbidden_sets_are_disjoint() -> None:
    assert not ALLOWED_KEYS & FORBIDDEN_KEYS
    for key in ("filename", "path", "content", "text", "url", "query", "body"):
        assert key in FORBIDDEN_KEYS


def test_structlog_drops_unknown_and_sensitive_keys(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json_output=True)
    get_logger("test").info(
        "upload_received",
        job_id="3f2a9c4e7b1d4e6f8a0b5c7d9e1f2a3b",
        tool_slug="merge-pdf",
        filename=CANARIES[0],
        content=CANARIES[1],
        text=CANARIES[2],
        url=CANARIES[3],
        query="token=CANARY-query",
        body=CANARIES[1],
        authorization=CANARIES[4],
        cookie=CANARIES[5],
        path=CANARIES[6],
        whatever="CANARY-unknown-key",
    )
    out = capsys.readouterr().out
    for canary in [*CANARIES, "CANARY-unknown-key", "CANARY-query"]:
        assert canary not in out
    (line,) = _lines(out)
    assert line["event"] == "upload_received"
    assert line["job_id"] == "3f2a9c4e7b1d4e6f8a0b5c7d9e1f2a3b"
    assert line["tool_slug"] == "merge-pdf"
    assert set(line) <= ALLOWED_KEYS


def test_exceptions_logged_as_class_name_only(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json_output=True)
    log = get_logger("test")
    try:
        raise ValueError(f"cannot parse {CANARIES[6]}")
    except ValueError:
        log.exception("parse_failed")
    out = capsys.readouterr().out
    assert CANARIES[6] not in out
    assert "Traceback" not in out
    (line,) = _lines(out)
    assert line["error_class"] == "ValueError"


def test_stdlib_records_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json_output=True)
    std = logging.getLogger("uvicorn.error")
    try:
        raise OSError(f"disk error at {CANARIES[6]}")
    except OSError:
        std.exception("Exception in ASGI application", extra={"filename_x": CANARIES[0]})
    out = capsys.readouterr().out
    assert CANARIES[6] not in out
    assert CANARIES[0] not in out
    (line,) = _lines(out)
    assert line["logger"] == "uvicorn.error"
    assert line["error_class"] == "OSError"


def test_http_client_info_logs_suppressed(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json_output=True)
    logging.getLogger("httpx").info("HTTP Request: GET %s", CANARIES[3])
    assert CANARIES[3] not in capsys.readouterr().out


def test_values_are_single_line_and_bounded() -> None:
    cleaned = redact_mapping({"event": "x\ny" + "a" * 500, "filename": "nope"})
    assert "filename" not in cleaned
    assert "\n" not in cleaned["event"]
    assert len(cleaned["event"]) <= 203


def test_console_renderer_also_redacts(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json_output=False)
    get_logger("test").info("hello", filename=CANARIES[0])
    out = capsys.readouterr().out
    assert "hello" in out
    assert CANARIES[0] not in out
    configure_logging("INFO", json_output=True)

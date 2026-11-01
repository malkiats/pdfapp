"""Helpers to declare contract responses on routes (docs/api.md section 8)."""

from __future__ import annotations

from typing import Any

from pdfapp.backend.app.schemas.generated.models import Problem

PROBLEM_DESCRIPTIONS: dict[str, str] = {
    "400": "Malformed request (unparseable multipart or JSON). Not for field validation.",
    "404": "Resource not found.",
    "422": "Well-formed but semantically invalid. Several codes share this status.",
    "429": "Rate limited (`rate_limited`) or daily quota exhausted (`quota_exceeded`).",
    "5XX": "Server-side failure.",
}


def problem_responses(*statuses: str) -> dict[int | str, dict[str, Any]]:
    """`responses=` entries rendered with the Problem model. The app's OpenAPI hook moves
    their media type to application/problem+json."""
    return {
        status: {"model": Problem, "description": PROBLEM_DESCRIPTIONS.get(status, "Error.")}
        for status in statuses
    }

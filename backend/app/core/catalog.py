"""Tool catalog loader.

``shared/tool-catalog.json`` is the single source of truth for the backend and the frontend.
It is loaded and validated once at startup, and the app refuses to start if it is invalid:

1. JSON Schema validation against ``shared/tool-catalog.schema.json`` (Draft 2020-12),
   including catalog-only rules such as "file tools list at least one MIME type".
2. Validation of every entry against the generated contract model ``Tool``.
3. Unique slugs (not expressible in JSON Schema).

Entries are served unchanged (the raw validated dicts), in catalog order.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.schemas.generated.models import Tool

log = get_logger(__name__)


class CatalogError(RuntimeError):
    """The catalog file is missing or invalid. Raised at startup (fail fast)."""


@dataclass(frozen=True)
class Catalog:
    schema_version: int
    entries: tuple[Mapping[str, Any], ...]
    _by_slug: Mapping[str, Mapping[str, Any]] = field(repr=False)

    def get(self, slug: str) -> Mapping[str, Any] | None:
        return self._by_slug.get(slug)

    def filter(
        self, *, category: str | None = None, status: str | None = None
    ) -> list[Mapping[str, Any]]:
        return [
            entry
            for entry in self.entries
            if (category is None or entry["category"] == category)
            and (status is None or entry["status"] == status)
        ]

    def __len__(self) -> int:
        return len(self.entries)


def _read_json(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogError(f"{what} not found at the configured path") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{what} is not readable JSON ({type(exc).__name__})") from exc


def validate_catalog_document(document: Any, schema: Mapping[str, Any] | None) -> list[str]:
    """Returns a list of human-readable problems (empty when valid)."""
    problems: list[str] = []
    if schema is not None:
        validator = Draft202012Validator(schema)
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.path)):
            pointer = "/" + "/".join(str(p) for p in error.path)
            problems.append(f"{pointer}: {error.message}")
    if not isinstance(document, dict) or not isinstance(document.get("tools"), list):
        problems.append("/tools: missing or not a list")
        return problems
    seen: set[str] = set()
    for index, entry in enumerate(document["tools"]):
        try:
            Tool.model_validate(entry)
        except ValidationError as exc:
            problems.append(f"/tools/{index}: does not match contract Tool ({exc.error_count()})")
            continue
        slug = entry["slug"]
        if slug in seen:
            problems.append(f"/tools/{index}/slug: duplicate slug {slug!r}")
        seen.add(slug)
    return problems


def load_catalog(path: Path, schema_path: Path | None) -> Catalog:
    document = _read_json(path, "tool catalog")
    schema: Mapping[str, Any] | None = None
    if schema_path is not None and schema_path.exists():
        schema = _read_json(schema_path, "tool catalog schema")
    else:
        log.warning("catalog_schema_missing", stage="catalog")
    problems = validate_catalog_document(document, schema)
    if problems:
        shown = "; ".join(problems[:10])
        raise CatalogError(f"tool catalog is invalid ({len(problems)} problems): {shown}")
    entries: Sequence[Mapping[str, Any]] = tuple(document["tools"])
    return Catalog(
        schema_version=int(document["schema_version"]),
        entries=tuple(entries),
        _by_slug={entry["slug"]: entry for entry in entries},
    )


def etag_for(body: bytes) -> str:
    """Strong ETag of a representation."""
    return '"' + hashlib.sha256(body).hexdigest()[:32] + '"'


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """RFC 9110 weak comparison for If-None-Match."""
    if not if_none_match:
        return False
    candidates = [c.strip() for c in if_none_match.split(",")]
    if "*" in candidates:
        return True
    bare = etag.removeprefix("W/")
    return any(c.removeprefix("W/") == bare for c in candidates)

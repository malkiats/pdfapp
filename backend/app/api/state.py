"""Process-wide application context, attached to ``app.state.ctx`` by the app factory."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request
from redis.asyncio import Redis

from pdfapp.backend.app.core.catalog import Catalog
from pdfapp.backend.app.core.config import Settings
from pdfapp.backend.app.storage import TempFileManager


@dataclass
class AppContext:
    settings: Settings
    catalog: Catalog
    temp_files: TempFileManager
    redis: Redis | None
    # Serialized catalog representations keyed by (category, status) filter.
    tool_list_cache: dict[tuple[str | None, str | None], tuple[bytes, str]] = field(
        default_factory=dict
    )


def get_context(request: Request) -> AppContext:
    ctx = request.app.state.ctx
    assert isinstance(ctx, AppContext)
    return ctx

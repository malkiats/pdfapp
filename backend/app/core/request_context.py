"""Per-request context (request id) shared by middleware, error handlers and logging."""

from __future__ import annotations

import re
import secrets
from contextvars import ContextVar, Token
from typing import Final

REQUEST_ID_HEADER: Final = "X-Request-Id"
_REQUEST_ID_RE: Final = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def is_valid_request_id(value: str | None) -> bool:
    return value is not None and _REQUEST_ID_RE.fullmatch(value) is not None


def new_request_id() -> str:
    """`req_` + 16 URL-safe characters: matches ^[A-Za-z0-9_-]{8,64}$ and carries no data."""
    return "req_" + secrets.token_urlsafe(12)


def current_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str) -> Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)

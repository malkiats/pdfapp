"""Stateless upload ids for the large-file flow.

An id is ``<created:7 base36><count:1 base36><token:43 url-safe>``. The creation time
and file count are readable from the id itself, so the server needs no database to
derive the object-key prefix, the expiry and how many inputs to expect. The 256-bit
random token is the capability: guessing it is infeasible, and tampering with the
time or count fields only points at a different (empty) prefix.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

_TS_LEN: Final = 7  # base36, covers dates far beyond 2100
_TOKEN_BYTES: Final = 32  # token_urlsafe(32) -> 43 chars
_DIGITS: Final = "0123456789abcdefghijklmnopqrstuvwxyz"
MAX_FILES: Final = 20
# Strict format. Anything else is treated as unknown.
UPLOAD_ID_RE: Final = re.compile(r"^[0-9a-z]{7}[1-9a-k][A-Za-z0-9_-]{43}$")
# Max clock skew tolerated for ids "from the future".
_FUTURE_SKEW_SECONDS: Final = 60


@dataclass(frozen=True)
class UploadId:
    value: str
    created: int  # unix seconds
    count: int

    @property
    def hour_bucket(self) -> str:
        return hour_bucket(self.created)


def hour_bucket(unix_seconds: int) -> str:
    return datetime.fromtimestamp(unix_seconds, UTC).strftime("%Y%m%d%H")


def _b36(n: int, width: int) -> str:
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = _DIGITS[r] + out
    return out.rjust(width, "0")


def new_upload_id(now: int, count: int) -> UploadId:
    if not 1 <= count <= MAX_FILES:
        raise ValueError("count out of range")
    value = _b36(now, _TS_LEN) + _DIGITS[count] + secrets.token_urlsafe(_TOKEN_BYTES)
    return UploadId(value=value, created=now, count=count)


def parse_upload_id(value: str, now: int) -> UploadId | None:
    """Returns the parsed id, or None when the format is wrong or the time is in the future."""
    if not UPLOAD_ID_RE.fullmatch(value):
        return None
    created = int(value[:_TS_LEN], 36)
    if created > now + _FUTURE_SKEW_SECONDS:
        return None
    return UploadId(value=value, created=created, count=int(value[_TS_LEN], 36))

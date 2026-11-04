"""Rate-limit identity: the ASGI peer locally, Vercel's forwarding header on Vercel."""

from __future__ import annotations

from typing import Any

import pytest
from pdfapp.backend.app.middleware.rate_limit import scope_client_key


def _scope(peer: str, **headers: str) -> dict[str, Any]:
    return {
        "type": "http",
        "client": (peer, 1234),
        "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()],
    }


def test_off_vercel_headers_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    scope = _scope("203.0.113.9", x_forwarded_for="198.51.100.1", x_vercel_forwarded_for="1.2.3.4")
    assert scope_client_key(scope) == "203.0.113.9"


def test_on_vercel_uses_leftmost_vercel_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    scope = _scope(
        "10.0.0.1",
        x_vercel_forwarded_for="198.51.100.7, 10.0.0.2",
        x_forwarded_for="192.0.2.1",
    )
    assert scope_client_key(scope) == "198.51.100.7"


def test_on_vercel_falls_back_to_xff_then_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    assert scope_client_key(_scope("10.0.0.1", x_forwarded_for="192.0.2.5, 10.0.0.3")) == (
        "192.0.2.5"
    )
    assert scope_client_key(_scope("10.0.0.1")) == "10.0.0.1"


def test_ipv6_grouped_by_64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    a = scope_client_key(_scope("10.0.0.1", x_vercel_forwarded_for="2001:db8:1:2:aaaa::1"))
    b = scope_client_key(_scope("10.0.0.1", x_vercel_forwarded_for="2001:db8:1:2:ffff::9"))
    c = scope_client_key(_scope("10.0.0.1", x_vercel_forwarded_for="2001:db8:1:3::1"))
    assert a == b == "2001:db8:1:2::/64"
    assert c != a
    mapped = scope_client_key(_scope("10.0.0.1", x_vercel_forwarded_for="::ffff:192.0.2.8"))
    assert mapped == "192.0.2.8"


def test_garbage_header_is_one_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    assert scope_client_key(_scope("10.0.0.1", x_vercel_forwarded_for="not-an-ip")) == "invalid"

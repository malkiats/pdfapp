"""Server-side fetching of public web pages, with SSRF protection, and page comparison."""

from __future__ import annotations

import difflib
import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from pdfapp.backend.app.core.errors import ApiError
from pdfapp.backend.app.lib.common import ToolInput, ToolResult, text_result

_MAX_BYTES = 2_000_000
_TIMEOUT = 10
_MAX_REDIRECTS = 3
_USER_AGENT = "DocumentToolsBot/1.0 (+page comparison)"


def _blocked(pointer: str) -> ApiError:
    return ApiError(
        400,
        "url_blocked",
        detail="That address cannot be fetched.",
        errors=[{"pointer": pointer, "code": "url_blocked", "message": "Address not allowed."}],
    )


def _fetch_failed(pointer: str) -> ApiError:
    return ApiError(
        502,
        "upstream_fetch_failed",
        detail="The page could not be fetched.",
        errors=[{"pointer": pointer, "code": "upstream_fetch_failed", "message": "Fetch failed."}],
    )


def _resolve_public(host: str, port: int, pointer: str) -> str:
    """Resolve once and return a public IP. Refuses private, loopback, link-local, etc."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise _fetch_failed(pointer) from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise _blocked(pointer)
    return str(infos[0][4][0])


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to an already-vetted IP (no second DNS lookup) while verifying TLS for the host."""

    def __init__(self, host: str, ip: str, port: int) -> None:
        super().__init__(host, port, timeout=_TIMEOUT, context=ssl.create_default_context())
        self._ip = ip

    def connect(self) -> None:
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)  # type: ignore[attr-defined]


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, ip: str, port: int) -> None:
        super().__init__(host, port, timeout=_TIMEOUT)
        self._ip = ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


def fetch_page(url: str, pointer: str = "/url") -> str:
    """GET a public http(s) page and return its decoded body (HTML or text)."""
    for _ in range(_MAX_REDIRECTS + 1):
        parts = urlsplit(url.strip())
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise _blocked(pointer)
        if parts.username or parts.password:
            raise _blocked(pointer)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if port not in (80, 443, 8080, 8443):
            raise _blocked(pointer)
        ip = _resolve_public(parts.hostname, port, pointer)
        conn_cls = _PinnedHTTPSConnection if parts.scheme == "https" else _PinnedHTTPConnection
        conn = conn_cls(parts.hostname, ip, port)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        try:
            conn.request(
                "GET", path, headers={"User-Agent": _USER_AGENT, "Accept": "text/html,text/plain"}
            )
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location")
                if not location:
                    raise _fetch_failed(pointer)
                url = urljoin(url, location)
                continue
            if resp.status != 200:
                raise _fetch_failed(pointer)
            ctype = (resp.getheader("Content-Type") or "").lower()
            if ctype and not ("html" in ctype or ctype.startswith("text/")):
                raise _fetch_failed(pointer)
            body = resp.read(_MAX_BYTES + 1)[:_MAX_BYTES]
            charset = "utf-8"
            if "charset=" in ctype:
                charset = ctype.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
            try:
                return body.decode(charset, errors="replace")
            except LookupError:
                return body.decode("utf-8", errors="replace")
        except (OSError, http.client.HTTPException) as e:
            raise _fetch_failed(pointer) from e
        finally:
            conn.close()
    raise _fetch_failed(pointer)


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template", "svg", "head"}
    _BLOCK = {
        "p",
        "div",
        "br",
        "li",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "section",
        "article",
        "header",
        "footer",
        "td",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def compare_webpages(inp: ToolInput) -> ToolResult:
    if len(inp.urls) != 2:
        raise ApiError(400, "validation_error", detail="Enter two page addresses.")
    a = html_to_text(fetch_page(inp.urls[0], "/url_a")).splitlines()
    b = html_to_text(fetch_page(inp.urls[1], "/url_b")).splitlines()
    diff = list(difflib.unified_diff(a, b, "first page", "second page", lineterm="", n=2))
    added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
    removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
    body = "\n".join(diff) if diff else "No differences found in the text of the two pages."
    report = (
        "Web page text comparison\n"
        f"First:  {inp.urls[0]}\nSecond: {inp.urls[1]}\n"
        f"Lines added: {added}\nLines removed: {removed}\n"
        "Lines starting with '-' exist only on the first page, '+' only on the second.\n\n"
        f"{body}\n"
    )
    return text_result(report, "compare-webpages")

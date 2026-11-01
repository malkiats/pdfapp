# Security Model and Threat Outline

Status: accepted · Last updated: 2026-11-01 (final in-request design, ADR-0006/0007). Reviewed by security-reviewer at phase gates touching uploads, outbound fetch, auth or payments.

## 1. Threats and controls

| Threat | Controls |
|---|---|
| Crafted file → parser crash or code execution | Pure-Python/wheel libraries only, pinned and patched. Page (≤ 200), pixel (≤ 40 MP) and DPI (≤ 150) caps. The only secret in the function is the spend-capped Groq key. 60 s `maxDuration`. |
| Decompression / image bombs | `Image.MAX_IMAGE_PIXELS`, page caps, zip-entry and ratio caps on any zip input, output size cap |
| SSRF (webpage comparison) | §3 |
| Cross-request data leakage (fluid compute shares instances) | No module-level content caches. Request-scoped `scratch()` with random names, wiped in `finally`. |
| Abuse / cost exhaustion | Vercel Firewall rate limits if available on the plan, otherwise a best-effort per-instance limiter. 4 MB body cap. `maxDuration`. Groq account spend cap. |
| Secret leakage | §5 |

## 2. Upload validation
1. Body-size guard: the whole request must be ≤ 4 MB, checked against `Content-Length` and by a streaming counter. Outputs over 4 MB return `413 output_too_large`.
2. The `slug` must exist in the catalog with `status: available`. The number of inputs must be within `min_inputs`..`max_inputs`.
3. **Magic-byte sniffing**. The tool's `input_kinds` must include `file`, and the sniffed kind must map to a MIME type in its `accepts` list. The client's `Content-Type` and file extension are ignored.
4. The filename is discarded. Options are validated by a strict Pydantic model per tool (`extra="forbid"`, bounded values, page-range grammar).
5. Structural open with limits (pikepdf, Pillow). Failures map to generic error codes, never to parser messages.

## 3. SSRF guard (`services/comparison/fetcher.py`, the only outbound HTTP client)
- `http`/`https` on ports 80 and 443 only. No userinfo in URLs. URLs ≤ 2048 characters.
- Resolve DNS ourselves and reject loopback, private, link-local, CGNAT, multicast, reserved, and IPv6 ULA or mapped addresses. Then connect to the vetted IP, which defeats DNS rebinding. Loopback matters especially here: the serverless runtime exposes local endpoints.
- Redirects are followed manually (≤ 3) and every hop is re-validated. Connect timeout 3 s, total 10 s. Response capped at 5 MB, `text/html` or `text/plain` only. No cookies or auth headers are sent. No JavaScript is executed.

## 4. HTTP hardening
- **CORS**: an allowlist containing only the frontend origin (and Vercel preview origins outside production).
- **API response headers**:
  - `Strict-Transport-Security`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.
  - `Cache-Control: no-store` on every tool response.
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`.
  - `Content-Disposition: attachment` with a generic filename.
- **Frontend**: a nonce-based CSP that allows `connect-src` only to the API origin, plus HSTS, `frame-ancestors 'none'` and a restrictive `Permissions-Policy`.

## 5. Secrets
- Secrets come from Vercel environment variables. They have no defaults, and startup fails in production if one is missing. `NEXT_PUBLIC_*` is for public config only.
- Before Phase 7, the API's only secret is `GROQ_API_KEY`, which has a provider-side spend cap.
- From Phase 7, auth, payments and webhook secrets live in a **separate Vercel project**, never alongside the file-parsing functions.
- CI runs gitleaks, `pip-audit`, `npm audit`, and checks lockfiles.

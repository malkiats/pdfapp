# Engineering Privacy Model

Status: accepted · Last updated: 2026-11-01 (final in-request design, ADR-0006/0007). Audience: engineers. The public Privacy Policy is a separate legal document and must agree with this one.

## 1. Promise and its honest limits
Public line: "Your files. Your privacy. Our tools. Nothing stored permanently."

What we engineer:
- Each file is processed inside the request that uploads it. It lives only in memory and in a request-scoped temporary directory, which is deleted before the response completes.
- The result goes back in the same response.
- We have no database, file store or backups for user content.

Approved user-facing copy: "Your files are processed on the fly and deleted as soon as your result is sent back. We don't keep copies."

Never claim: "zero retention", "never touches a disk", or "no one can ever access".
- Temporary files briefly exist on the function's disk.
- Our hosting provider and, for AI tools, Groq handle the data in transit under their own terms (§3).

## 2. Data inventory

| Data | Where | Retention |
|---|---|---|
| Uploaded files, text, results | Function memory and `/tmp/<random>` | Deleted in `finally` within the request. Crash leftovers are removed when an instance starts (> 5 min old). |
| Original filenames | Browser only | Discarded by the API. Results use a generic name (`<slug>-result.<ext>`). |
| Compared URLs and fetched pages | Request memory | Not stored, not logged |
| AI prompts and outputs | Request memory, and Groq | Not stored or logged by us. Groq retention per its terms (§3). |
| Logs | Vercel logs | Per plan retention, allowlisted fields only (§4) |
| Accounts, payments | — | Not before Phase 7 |

## 3. Third parties

| Processor | Receives | Limitation to disclose |
|---|---|---|
| **Vercel** | All requests, including file bytes, plus IP, user agent and URL paths | Processes content in transit, and keeps request logs per its plan. We never put content in URLs or logs. |
| **Groq** (AI tools only, opt-in per request) | The text sent for that tool, plus the prompt | Groq's retention and training terms apply. Verify them and enable zero-retention where offered before launch. Shown in the consent notice. |
| **Target websites** (comparison) | Our server's request to the URL the user gave | The target site logs our fetch |

## 4. Logging rules (`core/logging.py`)
- **Allowlist**: `ts`, `level`, `event`, `request_id`, `tool_slug`, `route` (template), `method`, `status`, `duration_ms`, `size_bucket`, `page_count`, `error_code`, `error_class`, `ai_tokens_in`, `ai_tokens_out`. Anything else is dropped.
- Never logged:
  - file content, filenames, extracted text, prompts or outputs;
  - user-supplied URLs (only the scheme and an HMAC of the host);
  - query strings, bodies, or token-bearing headers;
  - parser exception messages (only the class name).
- Tests plant canary strings in a filename, the file content, a URL and a prompt, and assert none appear in the logs.

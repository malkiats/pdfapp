# API Contract Guide

Status: frozen, contract revision 2.0.0 (synchronous refreeze) · Owner: api-designer · Source of truth: [`shared/openapi.yaml`](../shared/openapi.yaml) (OpenAPI 3.1) and [`shared/tool-catalog.schema.json`](../shared/tool-catalog.schema.json)

This is the human summary. If this page and the spec disagree, the spec wins. A gap goes back to the api-designer, who changes the spec and re-freezes it. Nobody patches generated code.

**The model in one line**: one synchronous `POST /api/v1/{tool-slug}` per tool. The request carries the input, the response carries the result. No jobs, no polling, no tokens, no tickets, no presigned URLs, no cookies, no accounts. Nothing is stored.

## 1. Operations and phases

| Operation | Method and path | Phase |
|---|---|---|
| `getHealth` | `GET /health` | 1 |
| `getReadiness` | `GET /ready` | 1 |
| `listTools` | `GET /api/v1/tools` (catalog and limits) | 1 |
| `mergePdf` | `POST /api/v1/merge-pdf` | 2 |
| `splitPdf` | `POST /api/v1/split-pdf` (ZIP of parts) | 2 |
| `organizePdf` | `POST /api/v1/organize-pdf` (reorder, duplicate, delete pages) | 2 |
| `rotatePdf` | `POST /api/v1/rotate-pdf` | 2 |
| `compressPdf` | `POST /api/v1/compress-pdf` | 2 |
| `imageToPdf` | `POST /api/v1/image-to-pdf` | 2 |
| `pdfToImages` | `POST /api/v1/pdf-to-images` (ZIP of images) | 2 |
| `extractText` | `POST /api/v1/extract-text` (UTF-8 text) | 2 |
| `compareSites` | `POST /api/v1/compare-sites` (JSON in, JSON out) | 3 |

Every operation carries `x-phase`. A tool whose endpoint is not built yet is `coming_soon` in the catalog, and its route simply does not exist (the framework 404 is rendered as a `Problem` with code `not_found`). Frontend must not call a `coming_soon` tool. The `phase` numbers are informational and can be reassigned without a contract change.

## 2. Decisions on the five freeze questions

1. **Inline or presigned URL?** Inline. The result is the `200` response body with `Content-Disposition: attachment; filename="{slug}-result.{ext}"` (generated name, never the user's). Presigned URLs are dead: no storage, no tickets. The browser reads the response as a blob and offers it for download.
2. **Max size.** One cap on the **whole request body**, served by `GET /api/v1/tools` as `limits.max_request_bytes` (recommended default **25 MB = 26214400**) and `limits.max_pages` (default 100). It is a server setting, not hard-coded in clients. **Risk to verify before building:** Vercel Functions document a request and response body limit of about 4.5 MB, which is far below 25 MB. If that applies to this deployment, set the setting to the real limit (no contract change) and the product limit shrinks. If 25 MB is a hard product requirement, uploads cannot go through a Vercel Function and the contract would need a different transport. Treat any `413` as `file_too_large` even when the body is not `problem+json`, because the platform can emit it first.
3. **Options.** One optional multipart part named `options`: a JSON object sent with part Content-Type `application/json`, strictly validated (unknown keys rejected) against the tool's `*Options` schema (`MergePdfOptions`, `RotatePdfOptions`, ...). Page ranges are a string with the grammar `^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$`, 1-based, for example `"1-3,5,8-10"` (schema `PageRange`). `organize-pdf` takes `page_order` as an integer array. `compare-sites` has no files, so it takes a JSON body with `url_a`, `url_b` and an optional `options` object.
4. **Error detail.** Sanitized and from a fixed table. `title` and `detail` are fixed text per `code`; they never contain exception text, tool output, paths, filenames, content, submitted URLs or option values. Field problems add `errors[]` with a JSON Pointer (`/options/angle`) and a rule code. A processing failure is the generic `processing_failed` plus the `request_id` to quote.
5. **Rate limit.** Per client IP, one shared budget across all tool endpoints (not per endpoint, not global). Recommended default 20 requests per minute, a server setting. A global 1 req/s was rejected: one abuser would lock everyone out. Responses carry `RateLimit-Limit/Remaining/Reset`, and a 429 adds `Retry-After`. On serverless the counter needs a shared store (for example Vercel KV or Upstash). Without one, limits are per instance and only best-effort; `/ready` reports `rate_limiter: ok | failed | not_configured`.

## 3. Request and response conventions

- **File tools**: `multipart/form-data` with `file` (one file) or `files` (several, order is significant, used by merge and image-to-pdf), plus optional `options`. Part filenames and part Content-Types are ignored; the server sniffs magic bytes and checks them against the tool's `accepts`.
- **Responses**: `200` with the file (`application/pdf`, `application/zip`, or `text/plain; charset=utf-8`), or for `compare-sites` an `application/json` `CompareSitesResult` (`summary`, `diff[]`, `truncated`). Compress returns the original bytes if recompression would grow the file. Extract-text on a PDF with no text layer returns an empty file (there is no OCR).
- **No auth, no cookies** in this revision. CORS therefore needs no credentials. Adding optional auth later is additive.
- Browser flow: `fetch` the endpoint, `await res.blob()`, create an object URL, click a hidden `a[download]`. Show an indeterminate spinner (no progress is reported).

## 4. Errors

Every non-2xx response (except the `/ready` 503 body) is `application/problem+json` (RFC 9457) with `type` (`urn:problem:{code}`), `title`, `status`, `code`, `request_id`, and optionally `detail`, `instance`, `errors[]`, `retry_after_seconds`, `params` (scalars such as `limit_bytes`, `limit`). **Branch on `code`.**

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `bad_request` | Unparseable multipart or JSON |
| 400 | `validation_error` | Field validation failed (`errors[]`) |
| 400 | `too_many_files` | More files than the tool's `max_inputs` |
| 400 | `too_many_pages` | Over `limits.max_pages` (`params.limit`) |
| 400 | `unsupported_type` | Sniffed kind not in the tool's `accepts` |
| 400 | `type_mismatch` | Mixed or contradictory kinds in one request |
| 400 | `invalid_file` | Corrupt or unreadable document |
| 400 | `file_encrypted` | Password-protected PDF |
| 400 | `url_blocked` | Outbound-fetch guard refused a URL. The reason is never disclosed |
| 404 | `not_found` | No such route (also a `coming_soon` tool) |
| 413 | `file_too_large` | Body over `limits.max_request_bytes` |
| 429 | `rate_limited` | Sends `Retry-After`. Retry with backoff |
| 500 | `processing_failed` | The tool could not process the input (generic) |
| 500 | `internal_error` | Unexpected failure |
| 502 | `upstream_fetch_failed` | A page to compare could not be fetched (`compare-sites` only) |
| 504 | `processing_timeout` | Platform time budget exhausted |

Coordinator's four classes (400, 413, 429, 500) are kept as the core. 502 (target site problem, not our fault and not the client's input) and 504 (platform timeout) are added because folding them into 400 or 500 would mislead the UI and retry logic.

## 5. Headers and CORS

- `X-Request-Id` on every response (a client may supply its own, 8 to 64 chars `A-Za-z0-9_-`); it is echoed as `Problem.request_id`.
- `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` on tool and catalog responses; `Retry-After` on 429.
- `Cache-Control: no-store` on tool, probe and error responses. `GET /api/v1/tools` is cacheable (`ETag`, `If-None-Match` gives 304).
- CORS: allowlisted origins only, no credentials. Allow headers `Content-Type`, `X-Request-Id`, `If-None-Match`. Expose `X-Request-Id, Retry-After, RateLimit-Limit, RateLimit-Remaining, RateLimit-Reset, ETag, Content-Disposition`.

## 6. Versioning and compatibility

Path `/api/v1`. Additive changes are safe: optional request fields, new response fields, new values in response enums (`ToolCategory`, `OutputKind`, `ErrorCode`), new tool endpoints, new `*Options` schemas. Clients ignore unknown response properties and unknown enum values. Anything else is `/api/v2`. CI runs `oasdiff breaking <previous shared/openapi.yaml> shared/openapi.yaml` from the first release on. `info.version` is the contract revision. `/tools` is deliberately unpaginated (about a dozen entries).

## 7. Tool catalog

`shared/tool-catalog.json` (backend builder) has the shape `{ "schema_version": 2, "tools": [ Tool, ... ] }`, validated by `shared/tool-catalog.schema.json`. The API serves entries unchanged. The `$defs` in the schema are identical to the same-named `components.schemas` in `openapi.yaml` (a contract test enforces it). The CI catalog step also checks the catalog-only rules: unique slugs, file tools list `accepts` (the schema's `allOf`), and each `options_schema` names an existing schema. A tool's endpoint is always `POST /api/v1/{slug}`. `output_kind` is one of `pdf | zip | txt | json`. One example entry:

```json
{
  "slug": "merge-pdf",
  "category": "organize",
  "title": "Merge PDF",
  "description": "Combine several PDF files into one document, in the order you choose.",
  "icon": "combine",
  "input_kinds": ["file"],
  "accepts": ["application/pdf"],
  "min_inputs": 2,
  "max_inputs": 10,
  "options_schema": "MergePdfOptions",
  "output_kind": "pdf",
  "status": "coming_soon",
  "phase": 2,
  "seo": {
    "title": "Merge PDF files online, without keeping them",
    "description": "Combine PDF files into one in seconds. Your files are never stored: the result comes straight back in the response.",
    "keywords": ["merge pdf", "combine pdf", "join pdf files"],
    "faq": [
      {
        "question": "Are my files stored after merging?",
        "answer": "No. The file is processed in memory and the result is returned in the same request. Nothing is saved on our servers."
      }
    ]
  }
}
```

Categories: `organize, optimize, convert-to-pdf, convert-from-pdf, compare`. Suggested mapping: merge, split, organize, rotate are `organize`; compress is `optimize`; image-to-pdf is `convert-to-pdf`; pdf-to-images and extract-text are `convert-from-pdf`; compare-sites is `compare`.

## 8. Codegen (boundary code is generated, never hand-written)

### Frontend: `openapi-typescript` (types) + `openapi-fetch` (client)

```bash
cd frontend
npm i openapi-fetch@0.17.0 && npm i -D openapi-typescript@7.13.0
npx openapi-typescript ../shared/openapi.yaml --default-non-nullable false -o src/lib/api/schema.d.ts
```

Run it from `frontend/` (the repo-root `redocly.yaml` would otherwise be picked up by the generator). Add it as `"api:types"` and commit the output; CI regenerates and runs `git diff --exit-code`. Notes:

- `--default-non-nullable false` is required, otherwise fields with a `default` become required in request types.
- `createClient<paths>({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL })`. No credentials.
- File tools: pass a `bodySerializer` that builds the `FormData` yourself and appends `options` as `new Blob([JSON.stringify(opts)], { type: "application/json" })`, with `opts` typed as `components["schemas"]["RotatePdfOptions"]` etc. The generated body type shows file parts as `string` (`format: binary`), so give a dummy value or cast. Use `parseAs: "blob"` for the response. Verified: this type-checks with `tsc --strict`.
- Mock before the backend exists: `npx -y @stoplight/prism-cli@5.16.0 mock shared/openapi.yaml -p 4010`, then point `NEXT_PUBLIC_API_BASE_URL` at it. Pick an error with `Prefer: code=502, example=upstream_fetch_failed`. Prism limitation: it rejects repeated multipart `files` parts (merge-pdf, image-to-pdf) with a 400, so mock those two by stubbing in the client or testing with a single `file` tool.

### Backend: FastAPI is code-first, so the spec drives the models

**Rule: hand-mirrored Pydantic models are NOT allowed.** Every schema in `components.schemas` has exactly one Python definition, generated into `backend/app/schemas/generated/`. Nothing else under `app/schemas/` may declare a class that duplicates one. Routers use the generated models for `response_model`, for the `Problem` envelope, for the `compare-sites` JSON body, and to validate each tool's `options`.

```bash
cd backend
uv add --dev "datamodel-code-generator==0.87.0" ruff
uv run datamodel-codegen \
  --input ../shared/openapi.yaml --input-file-type openapi \
  --output app/schemas/generated/models.py \
  --output-model-type pydantic_v2.BaseModel --target-python-version 3.12 \
  --use-annotated --field-constraints --use-standard-collections --use-union-operator \
  --use-subclass-enum --use-schema-description --disable-timestamp --reuse-model \
  --strict-nullable --collapse-root-models --formatters ruff-format
```

Commit the output with a "generated, do not edit" banner (add an `__init__.py`); CI regenerates and runs `git diff --exit-code app/schemas/generated`. Verified on this spec: the command runs cleanly, all 60 spec examples validate against the generated models, and every `*Options` model rejects unknown keys (`extra="forbid"`).

How a file-tool route is written (the multipart `*Request` schemas are wire documentation and typed frontend inputs; the backend does not instantiate them):

```python
@router.post("/rotate-pdf", operation_id="rotatePdf", responses=CONTRACT_RESPONSES["rotatePdf"])
async def rotate_pdf(
    file: UploadFile,
    options: Annotated[str | None, Form()] = None,
) -> Response:
    opts = parse_options(RotatePdfOptions, options)   # model_validate_json(options or "{}"); on error raise as validation_error
    ...
```

Also required: route function and `operation_id` equal the contract `operationId` (`generate_unique_id_function=lambda r: r.name`); one exception handler renders every error (including FastAPI 404, 405 and its default 422) as `Problem` with text from the fixed table; declare `responses=` from the contract so the emitted OpenAPI carries the same status codes; never put exception text into a response or log.

**Drift test** `backend/tests/contract/test_openapi_matches_contract.py` must fail the build if any of these breaks:

1. Every contract operation with `x-phase <= IMPLEMENTED_PHASE` (a constant bumped per phase) exists in `app.openapi()` with the same method and path, and no extra `/api/v1` operation exists that the contract lacks.
2. `operationId` is equal per operation, and the set of documented status codes is equal after dropping FastAPI's auto-added `422 HTTPValidationError`.
3. Every schema reachable from an implemented operation is equal between the contract and `app.openapi()` after normalization. The normalizer drops `title`, `description`, `examples`, `x-*`, and treats `oneOf`/`anyOf` with `null` and `type: [X, "null"]` as the same. It compares `type`, `properties`, `required`, `enum`, `format`, `pattern`, length and range limits, and `additionalProperties`.
4. For each multipart operation, the part names and required flags that FastAPI emits equal the contract `*Request` schema properties (media type must be `multipart/form-data`).
5. Every `example` in the contract validates against its generated model.
6. `Tool` and the other catalog `$defs` equal `shared/tool-catalog.schema.json` (same normalizer, ignoring `allOf`), `shared/tool-catalog.json` validates with `jsonschema.Draft202012Validator`, slugs are unique, and every `options_schema` exists. Every catalog `slug` with `status: available` has a matching `POST /api/v1/{slug}` in `app.openapi()`.

### Lint and breaking-change checks

```bash
npx -y @redocly/cli@2.72.1 lint --config redocly.yaml shared/openapi.yaml   # repo-root strict config (+ .redocly.lint-ignore.yaml)
npx -y -p ajv-cli@5 -p ajv-formats@3 ajv validate --spec=draft2020 -c ajv-formats -s shared/tool-catalog.schema.json -d shared/tool-catalog.json
oasdiff breaking <previous-committed-spec> shared/openapi.yaml               # from the second release on
```

## 9. Deliberately omitted (right-sizing)

No auth, accounts, tiers or quotas (anonymous, one per-IP limit). No jobs, polling, tickets or presigned URLs. No AI tools and no consent field. No OCR. No `Idempotency-Key` (every call is a pure function of its input, so a retry is safe). No ETag/If-Match (nothing is mutable). No `GET /api/v1/tools/{slug}` (landing pages are generated from the catalog file). No webhooks.

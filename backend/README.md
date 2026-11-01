# Backend: Document Tools API, workers and sweeper

Python 3.12 · FastAPI · Pydantic v2 · RQ on Redis/Valkey · uv. One codebase, one image, several
roles (docs/architecture.md section 2). Phase 1 ships the foundation only: health probes, the
public tool catalog, the privacy-critical `TempFileManager`, worker/sweeper wiring. There is
no document processing yet; every tool in the catalog is `coming_soon`.

Contract: [`shared/openapi.yaml`](../shared/openapi.yaml) (wins over any other doc) ·
guide: [`docs/api.md`](../docs/api.md) · storage: [ADR-0002](../docs/adr/0002-temp-storage-and-cleanup.md)
· queue: [ADR-0001](../docs/adr/0001-job-queue.md).

## Run locally

```bash
cd backend
uv python install 3.12          # if 3.12 is not on PATH
uv sync                         # creates .venv from uv.lock (dev tools included)

# API on :8000 (health: /health, readiness: /ready, catalog: /api/v1/tools)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-server-header

# Workers and sweeper need Redis (e.g. `docker run --rm -p 6379:6379 valkey/valkey:8`)
export APP_REDIS__URL=redis://localhost:6379/0
uv run python -m app.workers worker-docs
uv run python -m app.workers worker-web
uv run python -m app.workers worker-ai
uv run python -m app.workers sweeper
```

Without `APP_REDIS__URL` the API still runs: `/ready` reports `redis: not_configured`, the
rate limiter and workspace index are in-memory (single process only). With a URL that cannot
be reached, `/ready` answers `503 {"status":"not_ready","checks":{"redis":"failed",...}}`.

Always start uvicorn with `--no-access-log --no-server-header`: access logs come from the app
middleware (route templates only, never query strings) and no version banner is sent.

`pip` users: `pip install -r requirements.txt` (hashed, exported from `uv.lock`; runtime only).
Re-export after changing dependencies:

```bash
uv export --format requirements-txt --no-dev --no-emit-project -o requirements.txt
```

## Quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app                 # strict on the whole app package
uv run pytest -q                # add --cov=app for coverage
```

`ruff` bans `tempfile` and `boto3` imports (ADR-0002: only `app/storage` touches workspace
bytes). Tests use `fakeredis`; no services are needed.

## Contract codegen (never hand-write contract models)

```bash
uv run datamodel-codegen \
  --input ../shared/openapi.yaml --input-file-type openapi \
  --output app/schemas/generated/models.py \
  --output-model-type pydantic_v2.BaseModel --target-python-version 3.12 \
  --use-annotated --field-constraints --use-standard-collections --use-union-operator \
  --use-subclass-enum --use-schema-description --disable-timestamp --reuse-model \
  --strict-nullable --collapse-root-models --formatters ruff-format
```

`tests/contract/test_openapi_matches_contract.py` fails when the served OpenAPI drifts from the
contract, when generated models are stale, or when a contract example does not validate.
Bump `IMPLEMENTED_PHASE` in that file when a phase ships its operations; later-phase
operations are reported as skipped ("not yet implemented"). Route function names equal
`operationId`s.

## Layout

| Path | What |
|---|---|
| `app/main.py` | app factory `create_app()`; `app` for uvicorn |
| `app/core/` | settings, logging + redaction, request id, error model, catalog loader, Redis clients |
| `app/middleware/` | request id + access log, security headers, catch-all 500, body-size cap, rate limit, problem+json handlers |
| `app/api/` | `/health`, `/ready`, `/api/v1/tools`, `/api/v1/tools/{slug}` |
| `app/schemas/generated/` | generated contract models (do not edit) |
| `app/storage/` | `TempFileManager`, `StorageBackend` port, `LocalBackend`, workspace index |
| `app/workers/` | `python -m app.workers <role>`, RQ queues, sweeper |

Adding the S3 backend (Phase 4): implement `StorageBackend` (`app/storage/backends/base.py`) in
`backends/s3.py`, add `"s3"` to `StorageSettings.backend`, register it in
`backends/build_backend`, and parametrize the storage tests over both backends (moto).

## Configuration

All settings use the `APP_` prefix; nested groups use `__`. Lists accept JSON or, for CORS
origins, comma-separated values. Secrets have no defaults and are typed `SecretStr`. Startup
fails on invalid configuration; in `prod` the variables marked "prod: required" must be set.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | `local`, `test`, `dev`, `staging`, `prod`. `prod` hides `/openapi.json` and enforces required secrets. |
| `APP_STORAGE__BACKEND` | `local` | Storage backend (`s3` arrives in Phase 4). |
| `APP_STORAGE__ROOT` | `backend/var/workspaces` | Workspace root for the local backend (container: `/data/workspaces`, shared volume). |
| `APP_STORAGE__WORK_DIR` | `backend/var/work` | Worker scratch root (container: `/work`, tmpfs). |
| `APP_REDIS__URL` | unset | **Secret.** Redis/Valkey URL. Required for workers, sweeper, and prod. |
| `APP_REDIS__SOCKET_TIMEOUT_SECONDS` | `2.0` | API-side Redis timeout. |
| `APP_SECURITY__IP_HASH_KEY` | unset | **Secret, prod: required, >= 32 chars.** HMAC key for rate-limit IP hashing. Random per process when unset outside prod. |
| `APP_SECURITY__HSTS_MAX_AGE_SECONDS` | `63072000` | HSTS max-age (0 disables the header). |
| `APP_CORS__ALLOWED_ORIGINS` | `http://localhost:3000` in local/test, else empty | Exact origins; no wildcard. prod: required, https only. |
| `APP_CORS__MAX_AGE_SECONDS` | `600` | Preflight cache. |
| `APP_RATE_LIMIT__ENABLED` | `true` | Anonymous rate limit on `/api/v1`. |
| `APP_RATE_LIMIT__BACKEND` | `auto` | `auto`, `redis`, `memory`. |
| `APP_RATE_LIMIT__REQUESTS_PER_WINDOW` | `120` | Requests per window per hashed client IP. |
| `APP_RATE_LIMIT__WINDOW_SECONDS` | `60` | Window length. |
| `APP_RATE_LIMIT__TRUSTED_PROXY_HOPS` | `0` | Reverse proxies in front of the API (set 1 behind one ALB). |
| `APP_LIMITS__{FREE,PERSONAL,PRO}__MAX_FILE_BYTES` | 25 MiB / 100 MiB / 250 MiB | Per-file cap per tier. |
| `APP_LIMITS__{FREE,PERSONAL,PRO}__MAX_FILES_PER_JOB` | 5 / 20 / 20 | Inputs per job per tier. |
| `APP_LIMITS__{FREE,PERSONAL,PRO}__MAX_PAGES` | 100 / 500 / 500 | Pages per document per tier. |
| `APP_LIMITS__{FREE,PERSONAL,PRO}__JOB_TIMEOUT_SECONDS` | 120 / 300 / 300 | Hard job timeout per tier. |
| `APP_LIMITS__MAX_REQUEST_BODY_BYTES` | `1048576` | Body cap on every route except job upload. |
| `APP_LIMITS__UPLOAD_OVERHEAD_BYTES` | `1048576` | Multipart framing allowance on `POST /api/v1/jobs`. |
| `APP_RETENTION__OUTPUT_TTL_SECONDS` | `3600` | Output deleted at most this long after creation. |
| `APP_RETENTION__DELIVERED_GRACE_SECONDS` | `120` | Output deleted this long after first download. |
| `APP_RETENTION__HARD_TTL_SECONDS` | `7200` | Everything older is removed unconditionally. |
| `APP_RETENTION__SWEEP_INTERVAL_SECONDS` | `300` | Sweeper period. |
| `APP_RETENTION__TOMBSTONE_TTL_SECONDS` | `600` | Content-free deletion tombstone lifetime. |
| `APP_RETENTION__SWEEP_BATCH_LIMIT` | `1000` | Index entries per sweep. |
| `APP_PLANS__{PERSONAL,PRO}__AMOUNT` | `2.99` / `5.99` | Display prices (Phase 1: display only). |
| `APP_PLANS__{PERSONAL,PRO}__CURRENCY` | `USD` | ISO 4217 code. |
| `APP_QUEUES__DOCS` / `__WEB` / `__AI` | `["docs"]` / `["web"]` / `["ai"]` | Queues per worker role, priority order. |
| `APP_QUEUES__RESULT_TTL_SECONDS` | `600` | RQ result TTL. |
| `APP_QUEUES__SWEEPER_LOCK_TTL_SECONDS` | `240` | Sweeper Redis lock TTL. |
| `APP_LOGGING__LEVEL` | `INFO` | Root log level. |
| `APP_LOGGING__JSON_OUTPUT` | `true` | JSON lines, or console format when false. |
| `APP_CATALOG__PATH` | `<repo>/shared/tool-catalog.json` | Catalog file (image: `/srv/shared/tool-catalog.json`). |
| `APP_CATALOG__SCHEMA_PATH` | `<repo>/shared/tool-catalog.schema.json` | Schema validated at startup (skipped with a warning if absent). |

## Logging and privacy

Logs are JSON with an allowlist of keys (`app/core/logging.py`): anything else (filenames,
paths, content, text, URLs, queries, bodies, tokens, cookies, auth headers) is dropped, and
exceptions are logged as their class name only. Third-party records (uvicorn, rq) pass through
the same filter; `httpx`/`httpcore` are limited to warnings because they log request URLs.
RQ workers run with `log_job_description=False`.

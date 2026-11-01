# Document Tools

> Your files. Your privacy. Our tools. Nothing stored permanently.

A privacy-first, browser-based suite of document tools (PDF organise/convert/edit, OCR, web compare, AI helpers). Uploaded files live only as long as processing and delivery need them, then they are deleted, with a scheduled sweeper as a safety net. We do not claim absolute zero retention: see [docs/privacy.md](docs/privacy.md) for the exact limits.

**Status: Phase 1 (foundation).** No document processing ships yet. Phase 1 delivers the backend skeleton, the temp-file manager, the public tool catalog and the landing pages. See [docs/architecture.md §10](docs/architecture.md).

## Monorepo layout

```
backend/          FastAPI API + RQ workers (Python 3.12, uv). One image, several roles.
  Dockerfile      Multi-stage image for every backend role
frontend/         Next.js App Router site and tool UI (npm). Deployed on Vercel.
shared/           Frozen contracts: openapi.yaml, tool-catalog.json (+ JSON Schema)
docs/             Architecture, ADRs, API guide, security and privacy notes
infrastructure/   Docker helpers and deployment notes
compose.yaml      Local stack (valkey, api, workers, sweeper; optional db/mock/frontend)
Makefile          Developer entry points (`make help`)
.github/          CI workflow and Dependabot config
```

Backend roles (all from the same image, selected by command):

| Role | Command | Network |
|---|---|---|
| `api` | `uvicorn app.main:app` | internal + egress |
| `worker-docs` | `python -m app.workers worker-docs` | internal only (no internet) |
| `worker-web` | `python -m app.workers worker-web` | internal + egress |
| `worker-ai` | `python -m app.workers worker-ai` | internal + egress |
| `sweeper` | `python -m app.workers sweeper` | internal only |

## Prerequisites

- Docker with Compose v2.24 or later (Docker Desktop, Rancher Desktop, OrbStack or Docker Engine)
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 from `.python-version`)
- Node.js 24 LTS (`.nvmrc`) and npm
- `make`, `openssl`

## Quick start

```bash
make setup     # creates .env with random local secrets, installs backend + frontend deps
make dev       # builds the backend image, starts the stack, waits until healthy
curl http://localhost:8000/health
```

Other useful targets (`make help` lists them all):

| Target | What it does |
|---|---|
| `make dev-all` | Stack plus postgres, the Prism mock and the Next.js dev server |
| `make mock` | Prism mock of `shared/openapi.yaml` on :4010 (frontend can work without a backend) |
| `make logs SERVICE=api` | Follow logs |
| `make test` / `make lint` / `make fmt` | Same checks as CI |
| `make codegen` | Regenerate backend models and frontend types from the contract |
| `make down` | Stop everything |
| `make clean` | Stop and delete the temp workspace volume and local caches |

Run the frontend on the host instead of in compose: `cd frontend && npm run dev`.

## Ports (all bound to 127.0.0.1)

| Port | Service | Notes |
|---|---|---|
| 8000 | API | `/health` (liveness), `/ready` (readiness), `/api/v1/*` |
| 3000 | Frontend | `--profile frontend` or host `npm run dev` |
| 4010 | Prism mock | `--profile mock` |
| — | Valkey, Postgres | Internal network only, not published. Use `docker compose exec valkey valkey-cli`. |

## Local privacy and sandboxing notes

- The shared temp workspace is a **RAM-backed tmpfs volume**: documents are never written to your disk and vanish on `make clean` or when the stack stops.
- Valkey runs with no persistence (no RDB, no AOF).
- Backend containers run as UID 10001 with a read-only root filesystem, all capabilities dropped, `no-new-privileges`, and CPU, memory and PID limits. `worker-docs` sits on an `internal: true` network with no route to the internet.

## Documentation

| Document | Content |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Architecture, job lifecycle, sandboxing, deployment topology, phases |
| [docs/api.md](docs/api.md) | API contract guide, error codes, codegen commands |
| [docs/security.md](docs/security.md) | Threat model and controls |
| [docs/privacy.md](docs/privacy.md) | What we keep, for how long, and what we do not claim |
| [docs/adr/](docs/adr/) | Decision records (queue, temp storage, auth, PDF libraries, payments) |
| [infrastructure/deployment/README.md](infrastructure/deployment/README.md) | Vercel and AWS deployment outline |
| [infrastructure/deployment/VERCEL.md](infrastructure/deployment/VERCEL.md) | Step-by-step Vercel deployment (frontend + backend) |
| [infrastructure/deployment/LOCAL-RANCHER-DESKTOP.md](infrastructure/deployment/LOCAL-RANCHER-DESKTOP.md) | Step-by-step local run on Rancher Desktop |

## Licensing

The product is closed-source commercial software, so AGPL dependencies (for example PyMuPDF and Ghostscript) are avoided unless a commercial licence is in place. Library choices and their licences are recorded in [docs/adr/0004-pdf-and-conversion-libraries.md](docs/adr/0004-pdf-and-conversion-libraries.md). The backend image's optional native-tools target installs Tesseract, LibreOffice and qpdf only, and its build fails if Ghostscript is pulled in.

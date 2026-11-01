# syntax=docker/dockerfile:1.10
#
# Backend image: ONE image for every role (architecture.md §2). The role is
# selected by the command, not by a separate image:
#
#   api          uvicorn app.main:app ...            (default CMD below)
#   worker-docs  python -m app.workers worker-docs
#   worker-web   python -m app.workers worker-web
#   worker-ai    python -m app.workers worker-ai
#   sweeper      python -m app.workers sweeper
#
# Build context is backend/. The shared tool catalog lives outside it, so it is
# passed as a named build context (BuildKit):
#
#   docker build -f backend/Dockerfile --build-context shared=shared backend
#
# Targets:
#   runtime             (default, last stage) - Phase 1 image, no native document tools
#   runtime-docs-native (opt-in)               - adds Tesseract, LibreOffice, qpdf for
#                                               worker-docs from Phase 3. NOT built by default:
#   docker build -f backend/Dockerfile --build-context shared=shared --target runtime-docs-native backend
#
# Runtime contract (sandboxing, architecture.md §7):
#   - runs as UID/GID 10001, no shell login, no sudo
#   - read-only root filesystem friendly: the only writable paths are
#     /tmp (tmpfs), /work (per-worker scratch tmpfs) and /data/workspaces
#     (the shared temp workspace volume, LocalBackend). Nothing else is written.
#   - no compilers or build tools in the final stage

# Base images are pinned by tag AND digest, written inline (not via ARG) so
# Dependabot can update them. Keep the two python FROM lines identical.

# ---------------------------------------------------------------------------
# uv binary only (pinned by digest)
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv

# ---------------------------------------------------------------------------
# builder: resolve and install locked dependencies into /srv/backend/.venv
# ---------------------------------------------------------------------------
FROM python:3.15.0-slim-trixie@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58 AS builder

COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/srv/backend/.venv \
    UV_NO_CACHE_DIR_WARNING=1

WORKDIR /srv/backend

# 1) dependencies only: this layer is reused until pyproject.toml / uv.lock change.
#    --locked fails the build if uv.lock is out of date with pyproject.toml.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --no-install-project

# 2) the project itself. .dockerignore keeps tests, caches and .venv out.
COPY . /srv/backend
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---------------------------------------------------------------------------
# base-runtime: minimal OS + venv + app, non-root
# ---------------------------------------------------------------------------
FROM python:3.15.0-slim-trixie@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58 AS base-runtime

# Writable mount points /work and /data/workspaces are created here, owned by
# 10001 with mode 0700; tmpfs / volumes are mounted over them at runtime.
# apt packages are not version-pinned on purpose (DL3008): the base image is
# pinned by digest, and Debian security updates must not break the build.
# pip is removed from the runtime: dependencies come only from the locked venv,
# and an installer in the image is attack surface.
# tini as PID 1: forwards signals and reaps zombies. RQ forks a work-horse per
# job and tools (soffice, tesseract) spawn grandchildren; without an init they
# would be left as zombies after timeouts kill the horse.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/* \
 && rm -rf /usr/local/lib/python3.12/site-packages/pip /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12 \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid 10001 --no-create-home \
      --home-dir /nonexistent --shell /usr/sbin/nologin app \
 && mkdir -p /work /data/workspaces \
 && chown 10001:10001 /work /data/workspaces \
 && chmod 0700 /work /data/workspaces

# Code and venv are owned by root and only readable by the app user, so a
# compromised process cannot modify the application even without read_only.
COPY --from=builder --chown=root:root /srv/backend /srv/backend
# Single source of truth for the tool catalog (architecture.md §10.1). Kept at
# the same relative position as in the repo: /srv/shared next to /srv/backend.
# `shared` is a named build context (--build-context shared=shared), not a stage.
# The backend resolves both files relative to the repo root (/srv here).
# hadolint ignore=DL3022
COPY --from=shared --chown=root:root tool-catalog.json tool-catalog.schema.json /srv/shared/

# Container healthcheck. Role-aware via CONTAINER_ROLE (set per service):
#   api           -> GET http://127.0.0.1:8000/health (liveness, no dependencies)
#   anything else -> PING the queue broker (workers are useless without it)
# Uses only the stdlib and redis-py (an RQ dependency), so no curl in the image.
COPY --chmod=0555 <<'EOF' /usr/local/bin/healthcheck
#!/srv/backend/.venv/bin/python
import os
import sys
import urllib.request

role = os.environ.get("CONTAINER_ROLE", "api")
try:
    if role == "api":
        port = os.environ.get("PORT", "8000")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
            sys.exit(0 if r.status == 200 else 1)
    url = os.environ.get("HEALTHCHECK_REDIS_URL") or os.environ.get("APP_REDIS__URL")
    if not url:
        sys.exit(0)  # no broker configured: process liveness is all we can assert
    import redis  # provided by the venv (rq dependency)

    redis.Redis.from_url(url, socket_timeout=3, socket_connect_timeout=3).ping()
    sys.exit(0)
except Exception:  # never print details: they could contain a URL with credentials
    sys.exit(1)
EOF

# HOME/XDG_CACHE_HOME/TMPDIR point at the /tmp tmpfs for libraries that insist
# on a writable home or cache directory.
ENV PATH="/srv/backend/.venv/bin:${PATH}" \
    VIRTUAL_ENV=/srv/backend/.venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    TMPDIR=/tmp \
    APP_CATALOG__PATH=/srv/shared/tool-catalog.json \
    APP_CATALOG__SCHEMA_PATH=/srv/shared/tool-catalog.schema.json \
    APP_STORAGE__ROOT=/data/workspaces \
    APP_STORAGE__WORK_DIR=/work \
    CONTAINER_ROLE=api \
    PORT=8000

WORKDIR /srv/backend
USER 10001:10001

ENTRYPOINT ["/usr/bin/tini", "--"]

# ---------------------------------------------------------------------------
# runtime-docs-native (OPT-IN, Phase 3+): native document tools for worker-docs
#
#   - tesseract-ocr (+ English data)        Apache-2.0
#   - LibreOffice headless, no GUI          MPL-2.0
#   - qpdf                                  Apache-2.0
#
# Ghostscript is deliberately NOT installed (AGPL, ADR-0004). The build fails if
# any package pulls it in transitively. Not built in Phase 1; build explicitly
# with --target runtime-docs-native. Only worker-docs should run this image.
# ---------------------------------------------------------------------------
FROM base-runtime AS runtime-docs-native
USER 0:0
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-eng \
      libreoffice-core-nogui \
      libreoffice-writer-nogui \
      libreoffice-calc-nogui \
      libreoffice-impress-nogui \
      qpdf \
      fonts-dejavu-core \
      fonts-liberation2 \
 && rm -rf /var/lib/apt/lists/* \
 && if dpkg -s ghostscript >/dev/null 2>&1 || command -v gs >/dev/null 2>&1; then \
      echo "ghostscript must not be installed (ADR-0004)" >&2; exit 1; \
    fi
ENV OMP_THREAD_LIMIT=1 \
    CONTAINER_ROLE=worker-docs
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["/usr/local/bin/healthcheck"]
CMD ["python", "-m", "app.workers", "worker-docs"]

# ---------------------------------------------------------------------------
# runtime (DEFAULT, last stage): Phase 1 image for every role
# ---------------------------------------------------------------------------
FROM base-runtime AS runtime
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD ["/usr/local/bin/healthcheck"]
# Access logging is done by the app middleware (route templates only), so
# uvicorn's own access log is off. No Server banner (security.md §5).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--no-access-log", "--no-server-header", "--timeout-graceful-shutdown", "20"]

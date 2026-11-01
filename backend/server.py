"""Vercel entrypoint (`[tool.vercel] entrypoint` in pyproject.toml). Not used by Docker."""

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Vercel Functions can only write under /tmp; the catalog is copied here by scripts/vercel_build.py.
os.environ.setdefault("APP_STORAGE__ROOT", "/tmp/doctools/workspaces")  # noqa: S108
os.environ.setdefault("APP_STORAGE__WORK_DIR", "/tmp/doctools/work")  # noqa: S108
os.environ.setdefault("APP_CATALOG__PATH", str(_HERE / "shared" / "tool-catalog.json"))
os.environ.setdefault(
    "APP_CATALOG__SCHEMA_PATH", str(_HERE / "shared" / "tool-catalog.schema.json")
)
# Vercel's edge replaces X-Forwarded-For with the real client IP.
os.environ.setdefault("APP_RATE_LIMIT__TRUSTED_PROXY_HOPS", "1")
# Redis added from the Vercel Marketplace (Upstash) injects REDIS_URL / KV_URL.
_marketplace_redis = os.environ.get("REDIS_URL") or os.environ.get("KV_URL")
if _marketplace_redis:
    os.environ.setdefault("APP_REDIS__URL", _marketplace_redis)

from pdfapp.backend.app.main import create_app  # noqa: E402

app = create_app()

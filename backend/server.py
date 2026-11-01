"""Vercel entrypoint (`[tool.vercel] entrypoint` in pyproject.toml). Not used by Docker."""

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Vercel can run the backend with `backend/` as the project root. Map the
# repository-style imports used in the source tree onto the deployed package.
sys.path.insert(0, str(_HERE))

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

import app as app_package  # noqa: E402

# Allow modules written as `pdfapp.backend.app.*` to resolve when the backend
# directory is the deployment root instead of the repository root.
import types

pdfapp_package = types.ModuleType("pdfapp")
pdfapp_package.__path__ = [str(_HERE.parent)]  # type: ignore[attr-defined]
sys.modules.setdefault("pdfapp", pdfapp_package)

pdfapp_backend_package = types.ModuleType("pdfapp.backend")
pdfapp_backend_package.__path__ = [str(_HERE)]  # type: ignore[attr-defined]
sys.modules.setdefault("pdfapp.backend", pdfapp_backend_package)

sys.modules.setdefault("pdfapp.backend.app", app_package)

from app.main import create_app  # noqa: E402

app = create_app()

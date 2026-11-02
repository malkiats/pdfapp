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

import types  # noqa: E402

# Allow repository-style imports (`pdfapp.backend.app.*`) to resolve when
# Vercel deploys the backend directory as an isolated project root.
pdfapp_package = types.ModuleType("pdfapp")
pdfapp_package.__path__ = []  # type: ignore[attr-defined]
sys.modules.setdefault("pdfapp", pdfapp_package)

pdfapp_backend_package = types.ModuleType("pdfapp.backend")
pdfapp_backend_package.__path__ = [str(_HERE)]  # type: ignore[attr-defined]
sys.modules.setdefault("pdfapp.backend", pdfapp_backend_package)

pdfapp_app_package = types.ModuleType("pdfapp.backend.app")
pdfapp_app_package.__path__ = [str(_HERE / "app")]  # type: ignore[attr-defined]
sys.modules.setdefault("pdfapp.backend.app", pdfapp_app_package)

try:
    from pdfapp.backend.app.main import create_app  # noqa: E402

    app = create_app()
except Exception as exc:
    # Keep the function invocable even if application startup fails. This
    # exposes only the exception type/message, not stack traces or secrets.
    import traceback  # noqa: F401
    from fastapi import FastAPI  # noqa: E402

    # Log the full traceback for debugging
    tb = traceback.format_exc()
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    print(f"ERROR: Failed to create app: {error_msg}", flush=True)
    print(tb, flush=True)

    fallback = FastAPI(title="Document Tools API - startup error", docs_url=None)

    @fallback.get("/")
    @fallback.get("/health")
    async def startup_error_root():
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

    app = fallback

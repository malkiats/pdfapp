"""Vercel entrypoint (`[tool.vercel] entrypoint` in pyproject.toml). Not used by Docker."""

import os
import sys
import types
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Vercel can run the backend with `backend/` as the project root. Map the
# repository-style imports used in the source tree onto the deployed package.
sys.path.insert(0, str(_HERE))

# scripts/vercel_build.py copies the shared catalog into backend/shared at build time.
os.environ.setdefault("APP_CATALOG__PATH", str(_HERE / "shared" / "tool-catalog.json"))

# Allow repository-style imports (`pdfapp.backend.app.*`) to resolve when
# Vercel deploys the backend directory as an isolated project root.
for _name, _path in (
    ("pdfapp", []),
    ("pdfapp.backend", [str(_HERE)]),
    ("pdfapp.backend.app", [str(_HERE / "app")]),
):
    _module = types.ModuleType(_name)
    _module.__path__ = _path  # type: ignore[attr-defined]
    sys.modules.setdefault(_name, _module)

try:
    from pdfapp.backend.app.main import create_app

    app = create_app()
except Exception as exc:  # noqa: BLE001 - keep the function invocable and report why
    import traceback

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    traceback.print_exc()
    # Bind now: Python deletes `exc` when the except block ends.
    _startup_error = {
        "status": "error",
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }

    app = FastAPI(title="Document Tools API - startup error", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
    async def startup_error(path: str) -> dict[str, str]:
        return _startup_error

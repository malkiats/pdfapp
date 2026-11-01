"""FastAPI application for the synchronous, stateless document tools backend."""

from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pdfapp.backend.app.api import tools
from pdfapp.backend.app.core.config import get_settings
from pdfapp.backend.app.core.logging import configure_logging, get_logger
from pdfapp.backend.app.middleware.errors import register_exception_handlers
from pdfapp.backend.app.middleware.http import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from pdfapp.backend.app.middleware.rate_limit import InMemoryRateLimiter, RateLimitMiddleware
from pdfapp.backend.app.api import health

log = get_logger(__name__)

# Load catalog at module level
_CATALOG_PATH = Path(__file__).resolve().parents[2] / "shared" / "tool-catalog.json"
_catalog_data: dict | None = None
_catalog_etag: str | None = None


def _load_catalog() -> dict:
    """Load and cache the catalog with its ETag."""
    global _catalog_data, _catalog_etag
    if _catalog_data is None:
        with open(_CATALOG_PATH) as f:
            _catalog_data = json.load(f)
        # Simple ETag: hash of the catalog JSON
        catalog_json = json.dumps(_catalog_data, separators=(",", ":"), sort_keys=True)
        _catalog_etag = hashlib.md5(catalog_json.encode()).hexdigest()[:8]  # noqa: S324
        log.info("catalog_loaded", etag=_catalog_etag)
    return _catalog_data


def _get_catalog_etag() -> str:
    """Get the catalog ETag, loading if necessary."""
    _load_catalog()
    return _catalog_etag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup and shutdown."""
    log.info("app_startup")
    _load_catalog()
    yield
    log.info("app_shutdown")


def create_app(settings=None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    configure_logging()

    app = FastAPI(
        title="Document Tools API",
        version="2.0.0",
        docs_url="/docs" if settings.environment == "local" else None,
        redoc_url=None,
        openapi_url=None,  # No schema endpoint; use shared/openapi.yaml
        lifespan=lifespan,
    )

    # Middleware stack (order matters)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Phase 1: anonymous, no auth
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "If-None-Match", "X-Request-Id"],
        allow_credentials=False,
        max_age=300,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.limits.max_request_bytes)

    # Rate limiting middleware
    if settings.rate_limit.enabled:
        rate_limiter = InMemoryRateLimiter(
            requests_per_minute=settings.rate_limit.per_ip_per_minute
        )
        app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

    # Exception handlers
    register_exception_handlers(app)

    # Routes
    app.include_router(health.router, tags=["health"])
    app.include_router(tools.router, tags=["catalog", "tools"])

    # Store settings in app state for access in routes
    app.state.settings = settings
    app.state.catalog_data = _load_catalog()
    app.state.get_catalog_etag = _get_catalog_etag

    return app


# Lazy initialization: the app is created on first access
_app: FastAPI | None = None


def get_app() -> FastAPI:
    """Get or create the FastAPI app."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


# For ASGI servers (uvicorn, Vercel, etc.)
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


# Initialize at import time for Vercel
@app.on_event("startup")
def startup():
    """Load settings and configure on startup."""
    settings = get_settings()
    configure_logging()
    _load_catalog()
    log.info("app_ready", environment=settings.environment)


# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(tools.router, tags=["catalog", "tools"])

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "If-None-Match", "X-Request-Id"],
    allow_credentials=False,
    max_age=300,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

settings = get_settings()
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.limits.max_request_bytes)

if settings.rate_limit.enabled:
    rate_limiter = InMemoryRateLimiter(
        requests_per_minute=settings.rate_limit.per_ip_per_minute
    )
    app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

register_exception_handlers(app)

# Store state
app.state.settings = settings
app.state.catalog_data = _load_catalog()
app.state.get_catalog_etag = _get_catalog_etag

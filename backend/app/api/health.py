"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Final

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from pdfapp.backend.app.core.logging import get_logger

router = APIRouter(tags=["health"])
log = get_logger(__name__)

_NO_STORE: Final = {"Cache-Control": "no-store"}


@router.get(
    "/health",
    summary="Liveness probe",
    responses={200: {"description": "Process is alive."}},
)
async def getHealth() -> JSONResponse:  # noqa: N802 - function name equals operationId
    """Returns 200 whenever the process is up."""
    return JSONResponse({"status": "ok"}, headers=_NO_STORE)


@router.get(
    "/ready",
    summary="Readiness probe",
    responses={
        200: {"description": "Ready to serve."},
        503: {"description": "Not ready."},
    },
)
async def getReadiness() -> JSONResponse:  # noqa: N802 - function name equals operationId
    """Checks app readiness. Phase 1 has no external dependencies."""
    # For Phase 1, always ready (no Redis, no storage, just in-memory processing)
    return JSONResponse(
        {"status": "ready", "checks": {"rate_limiter": "not_configured"}},
        status_code=200,
        headers=_NO_STORE,
    )

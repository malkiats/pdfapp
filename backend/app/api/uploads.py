"""Large-file flow on Cloudflare R2: createUpload, runUploadedTool, deleteUpload.

1. createUpload validates the declared files and returns one presigned PUT per file.
2. The browser PUTs the bytes straight to R2 (never through this function).
3. runUploadedTool takes a one-shot lock, downloads the inputs into memory, deletes them
   from R2 straight away, runs the same handler as the inline route, stores the result and
   returns a presigned GET. Every terminal failure deletes what was uploaded.
4. deleteUpload removes everything under the upload prefix (client calls it when done).

Stateless: the upload id encodes its creation time and file count (core/upload_ids.py).
Logs carry event names, error classes and sizes only, never keys or URLs.
"""

from __future__ import annotations

import re
import secrets
import time
from datetime import UTC, datetime
from typing import Annotated, Any, Final

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse, Response
from pdfapp.backend.app.api.tool_runner import (
    Handler,
    accepted,
    bad,
    build_tool_input,
    check_file_count,
    check_options,
    execute,
    runnable_tool,
    validate_inputs,
)
from pdfapp.backend.app.api.tools import HANDLERS
from pdfapp.backend.app.core.config import R2Config, Settings
from pdfapp.backend.app.core.errors import PROBLEM_MEDIA_TYPE, ApiError
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.core.upload_ids import UploadId, new_upload_id, parse_upload_id
from pdfapp.backend.app.middleware.rate_limit import (
    InMemoryRateLimiter,
    hash_client,
    scope_client_key,
)
from pdfapp.backend.app.schemas.generated.models import (
    CreateUploadRequest,
    CreateUploadResponse,
    Problem,
    RunUploadedToolRequest,
    UploadResult,
)
from pdfapp.backend.app.storage.r2 import ObjectTooLarge, R2Store, R2Unavailable, UploadKeys
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])
log = get_logger(__name__)

UPLOAD_ID_PATTERN: Final = "^[A-Za-z0-9_-]{32,128}$"
SLUG_PATTERN: Final = "^[a-z0-9-]{1,64}$"
NO_STORE: Final = {"Cache-Control": "no-store"}
# A run may start a little after the PUT URLs expire (a slow upload that began in time).
RUN_GRACE_SECONDS: Final = 600
SWEEP_TIME_BUDGET_SECONDS: Final = 1.5
# The sweep runs on about 1 in SWEEP_ONE_IN createUpload calls.
SWEEP_ONE_IN: Final = 10
# Vercel kills the function at 60 s; stop well before that so cleanup still runs.
RUN_DEADLINE_SECONDS: Final = 45.0
_EXT_RE: Final = re.compile(r"^[a-z0-9]{1,8}$")


# ------------------------------------------------------------------ OpenAPI helpers
def _inline_schema(model: type[Problem]) -> dict[str, Any]:
    """The model's JSON schema with every $ref inlined, for non-JSON media types."""
    schema = model.model_json_schema(ref_template="#/$defs/{model}")
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                target = defs[node["$ref"].rsplit("/", 1)[-1]]
                rest = {k: v for k, v in node.items() if k != "$ref"}
                return resolve({**target, **rest})
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)  # type: ignore[no-any-return]


_PROBLEM_SCHEMA: Final = _inline_schema(Problem)


def _problems(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {
        code: {
            "description": "Problem details.",
            "content": {PROBLEM_MEDIA_TYPE: {"schema": _PROBLEM_SCHEMA}},
        }
        for code in codes
    }


# ------------------------------------------------------------------ helpers
def _unavailable() -> ApiError:
    return ApiError(
        503, "large_files_unavailable", detail="Large file uploads are not available right now."
    )


def _require_r2(settings: Settings) -> R2Config:
    cfg = settings.r2()
    if cfg is None:
        raise _unavailable()
    return cfg


def _iso(unix_seconds: int) -> str:
    return datetime.fromtimestamp(unix_seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sweep_min_age(cfg: R2Config) -> int:
    # Never sweep an upload that could still be uploaded to, run, or downloaded from.
    return max(3600, 2 * cfg.presign_expires + RUN_GRACE_SECONDS)


def check_upload_rate(request: Request, op: str) -> None:
    """Tighter per-IP limit for the expensive upload operations (in-process, best effort)."""
    limiters: dict[str, InMemoryRateLimiter] | None = getattr(
        request.app.state, "upload_limiters", None
    )
    if not limiters or op not in limiters:
        return
    result = limiters[op].hit_now(hash_client(scope_client_key(request.scope)))
    if not result.allowed:
        raise ApiError(
            429,
            "rate_limited",
            detail="Slow down and retry shortly.",
            retry_after_seconds=result.reset_seconds,
        )


def _discard(
    store: R2Store,
    keys: list[str] | None = None,
    prefix: str | None = None,
    *,
    within: str | None = None,
) -> None:
    """Best-effort delete on a failure path; the sweep and lifecycle rule are the backstop."""
    try:
        if prefix is not None:
            store.delete_prefix(prefix)
        if keys:
            store.delete_keys(keys, within=within)
    except R2Unavailable as e:
        log.warning("r2_cleanup_failed", error_class=str(e))


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ApiError(504, "processing_timeout", detail="The operation took too long.")


def _require_file_tool(tool: dict[str, Any]) -> None:
    if "file" not in tool.get("input_kinds", []):
        raise bad("validation_error", "This tool does not take files.", "/tool")


def _incomplete(indexes: list[int]) -> ApiError:
    message = "File not uploaded or size mismatch."
    return ApiError(
        409,
        "upload_incomplete",
        detail="One or more files have not been fully uploaded.",
        errors=[
            {"pointer": f"/files/{i}", "code": "upload_incomplete", "message": message}
            for i in indexes[:50]
        ],
    )


# ------------------------------------------------------------------ createUpload
@router.post(
    "",
    operation_id="createUpload",
    summary="Start a large-file upload",
    status_code=201,
    response_model=CreateUploadResponse,
    responses=_problems(400, 404, 413, 429, 500, 503),
)
async def createUpload(request: Request, body: CreateUploadRequest) -> Response:  # noqa: N802
    check_upload_rate(request, "create")
    settings: Settings = request.app.state.settings
    cfg = _require_r2(settings)
    tool, _ = runnable_tool(request, body.tool, HANDLERS)
    _require_file_tool(tool)
    check_file_count(tool, len(body.files))

    limits = settings.limits
    total = 0
    for i, f in enumerate(body.files):
        if f.size > limits.max_large_file_bytes:
            raise ApiError(
                413,
                "file_too_large",
                detail="The upload exceeds the maximum size.",
                params={"limit_bytes": limits.max_large_file_bytes},
                errors=[{"pointer": f"/files/{i}/size", "code": "file_too_large",
                         "message": "File is larger than the limit."}],
            )  # fmt: skip
        if not accepted(f.content_type.value, tool.get("accepts", [])):
            raise bad("unsupported_type", "File type not accepted.", f"/files/{i}/content_type")
        total += f.size
    if total > limits.max_large_total_bytes:
        raise ApiError(
            413,
            "file_too_large",
            detail="The files together exceed the maximum size.",
            params={"limit_bytes": limits.max_large_total_bytes},
        )

    now = int(time.time())
    upload = new_upload_id(now, len(body.files))
    keys = UploadKeys.for_upload(cfg.prefix, upload)
    declared = [(f.content_type.value, f.size) for f in body.files]

    def presign() -> list[str]:
        store = R2Store(cfg)
        urls = [
            store.presign_put(keys.input(i), ctype, size, cfg.presign_expires)
            for i, (ctype, size) in enumerate(declared)
        ]
        if secrets.randbelow(SWEEP_ONE_IN) == 0:  # never raises
            R2Store(cfg, fast=True).sweep_stale(
                now=now, min_age_seconds=_sweep_min_age(cfg), time_budget=SWEEP_TIME_BUDGET_SECONDS
            )
        return urls

    try:
        urls = await run_in_threadpool(presign)
    except R2Unavailable as e:
        log.warning("r2_unavailable", op="create", error_class=str(e))
        raise _unavailable() from None

    log.info("upload_created", files=len(declared), input_bytes=total)
    return JSONResponse(
        status_code=201,
        headers=NO_STORE,
        content={
            "upload_id": upload.value,
            "expires_at": _iso(now + cfg.presign_expires),
            "files": [
                {
                    "index": i,
                    "put_url": url,
                    # The browser sets Content-Length itself from the Blob; it must match.
                    "headers": {"Content-Type": ctype, "Content-Length": str(size)},
                }
                for i, (url, (ctype, size)) in enumerate(zip(urls, declared, strict=True))
            ],
        },
    )


# ------------------------------------------------------------------ runUploadedTool
def _run_job(
    settings: Settings,
    cfg: R2Config,
    upload: UploadId,
    tool: dict[str, Any],
    handler: Handler,
    slug: str,
    options: dict[str, Any],
    text: str,
    ai_consent: bool,
    deadline: float,
) -> dict[str, Any]:
    """Blocking. Verifies, locks, downloads, deletes inputs, processes, stores the result.

    Inputs survive only the retryable 409 (an object missing or empty: PUT it and retry).
    Every other failure deletes the inputs, and any partially stored output.
    """
    limits = settings.limits
    store = R2Store(cfg)
    keys = UploadKeys.for_upload(cfg.prefix, upload)
    input_keys = [keys.input(i) for i in range(upload.count)]

    try:
        sizes = [store.head_size(k) for k in input_keys]
    except R2Unavailable:
        _discard(store, input_keys, within=keys.root)
        raise
    missing = [i for i, s in enumerate(sizes) if s is None or s < 1]
    if missing:
        raise _incomplete(missing)  # retryable: inputs kept
    oversize = [i for i, s in enumerate(sizes) if (s or 0) > limits.max_large_file_bytes]
    input_bytes = sum(s or 0 for s in sizes)
    if oversize or input_bytes > limits.max_large_total_bytes:
        _discard(store, input_keys, within=keys.root)
        raise _incomplete(oversize or list(range(upload.count)))

    # One-shot: a second run (concurrent or later) of the same upload is refused.
    try:
        first = store.create_once(keys.lock)
    except R2Unavailable:
        _discard(store, input_keys, within=keys.root)
        raise
    if not first:
        raise ApiError(409, "upload_incomplete", detail="This upload has already been processed.")

    inputs_deleted = False
    out_key: str | None = None
    succeeded = False
    try:
        files: list[bytes] = []
        for i, key in enumerate(input_keys):
            try:
                files.append(store.download_bytes(key, limits.max_large_file_bytes))
            except (FileNotFoundError, ObjectTooLarge):
                raise _incomplete([i]) from None
        # Everything is in memory: remove the inputs now, so a platform kill later in the
        # request cannot leave them behind.
        try:
            store.delete_keys(input_keys, within=keys.root)
            inputs_deleted = True
        except R2Unavailable as e:
            log.warning("r2_input_delete_failed", error_class=str(e))
        _check_deadline(deadline)

        validate_inputs(
            tool, files=files, urls=[], text=text, ai_consent=ai_consent, unsupported_status=415
        )
        tool_input = build_tool_input(
            settings,
            files=files,
            options=options,
            text=text,
            urls=[],
            max_pages=limits.max_large_pages,
            max_output_bytes=limits.max_large_total_bytes,
        )
        try:
            result = execute(handler, tool_input, slug)
        except ApiError as e:
            if e.code != "result_too_large":
                raise
            raise ApiError(422, "processing_failed", detail="The result is too large.") from None
        files.clear()
        size = len(result.content)
        if size > limits.max_large_total_bytes:
            raise ApiError(422, "processing_failed", detail="The result is too large.")
        _check_deadline(deadline)

        ext = result.filename.rsplit(".", 1)[-1].lower() if "." in result.filename else ""
        out_key = keys.output(ext if _EXT_RE.fullmatch(ext) else "bin")
        store.put_bytes(out_key, result.content, result.media_type)
        expires = int(time.time()) + cfg.presign_expires
        url = store.presign_get(out_key, result.filename, result.media_type, cfg.presign_expires)
        succeeded = True
        log.info("upload_run_succeeded", tool=slug, input_bytes=input_bytes, output_bytes=size)
        return {
            "download_url": url,
            "filename": result.filename,
            "media_type": result.media_type,
            "size": size,
            "expires_at": _iso(expires),
        }
    finally:
        if not succeeded:
            # Failure: leave nothing behind (inputs, partial output, and the lock, since
            # there is nothing left to protect).
            cleanup = [] if inputs_deleted else list(input_keys)
            if out_key is not None:
                cleanup.append(out_key)
            _discard(store, [*cleanup, keys.lock], within=keys.root)
        elif not inputs_deleted:
            _discard(store, input_keys, within=keys.root)


@router.post(
    "/{upload_id}/run/{slug}",
    operation_id="runUploadedTool",
    summary="Run a tool on uploaded files",
    response_model=UploadResult,
    responses=_problems(400, 404, 409, 415, 422, 429, 500, 503, 504),
)
async def runUploadedTool(  # noqa: N802
    request: Request,
    upload_id: Annotated[str, Path(pattern=UPLOAD_ID_PATTERN)],
    slug: Annotated[str, Path(pattern=SLUG_PATTERN)],
    body: RunUploadedToolRequest,
) -> Response:
    deadline = time.monotonic() + RUN_DEADLINE_SECONDS
    check_upload_rate(request, "run")
    settings: Settings = request.app.state.settings
    cfg = _require_r2(settings)
    now = int(time.time())
    upload = parse_upload_id(upload_id, now)
    if upload is None:
        raise ApiError(404, "not_found", detail="The requested resource does not exist.")
    inputs_prefix = UploadKeys.for_upload(cfg.prefix, upload).inputs

    try:
        if now > upload.created + cfg.presign_expires + RUN_GRACE_SECONDS:
            raise ApiError(404, "not_found", detail="The requested resource does not exist.")
        tool, handler = runnable_tool(request, slug, HANDLERS)
        _require_file_tool(tool)
        check_file_count(tool, upload.count)
        options = check_options(body.options if body.options is not None else {})
    except ApiError:
        # Terminal: this upload can never run as requested, so drop its inputs. Outputs of
        # an earlier successful run are left for deleteUpload.
        await run_in_threadpool(_discard, R2Store(cfg), None, inputs_prefix)
        raise

    try:
        payload = await run_in_threadpool(
            _run_job,
            settings,
            cfg,
            upload,
            tool,
            handler,
            slug,
            options,
            body.text or "",
            bool(body.ai_consent),
            deadline,
        )
    except R2Unavailable as e:
        log.warning("r2_unavailable", op="run", error_class=str(e))
        raise _unavailable() from None
    return JSONResponse(content=payload, headers=NO_STORE)


# ------------------------------------------------------------------ deleteUpload
@router.delete(
    "/{upload_id}",
    operation_id="deleteUpload",
    summary="Delete an upload",
    status_code=204,
    response_class=Response,
    responses=_problems(400, 429, 500),
)
async def deleteUpload(  # noqa: N802
    request: Request,
    upload_id: Annotated[str, Path(pattern=UPLOAD_ID_PATTERN)],
) -> Response:
    settings: Settings = request.app.state.settings
    cfg = settings.r2()
    upload = parse_upload_id(upload_id, int(time.time())) if cfg is not None else None
    if cfg is not None and upload is not None:
        root = UploadKeys.for_upload(cfg.prefix, upload).root
        try:
            deleted = await run_in_threadpool(lambda: R2Store(cfg).delete_prefix(root))
        except R2Unavailable as e:
            log.warning("r2_unavailable", op="delete", error_class=str(e))
            raise ApiError(
                500,
                "internal_error",
                detail="Something went wrong. Quote the request id if you contact support.",
            ) from None
        log.info("upload_deleted", objects=deleted)
    return Response(status_code=204, headers=NO_STORE)

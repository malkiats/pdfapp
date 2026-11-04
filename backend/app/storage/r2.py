"""Cloudflare R2 (S3-compatible) object store for the large-file flow.

A client is built per request from settings (ADR-0006 rule 3: no module-level request
data). Errors are re-raised as `R2Unavailable` carrying only the error class; object
keys, presigned URLs and credentials are never logged or put in exception messages.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pdfapp.backend.app.core.config import R2Config
from pdfapp.backend.app.core.logging import get_logger
from pdfapp.backend.app.core.upload_ids import UploadId, hour_bucket

S3Client = Any  # boto3 clients are untyped without the boto3-stubs package

log = get_logger(__name__)

# botocore DEBUG records contain URLs and keys; never let them through.
for _name in ("boto3", "botocore", "s3transfer", "urllib3"):
    logging.getLogger(_name).setLevel(logging.WARNING)

_DELETE_BATCH: Final = 1000
_CHUNK: Final = 1024 * 1024
_HOUR_DIR_RE: Final = re.compile(r"^[0-9]{10}$")
_SAFE_FILENAME_RE: Final = re.compile(r"[^A-Za-z0-9._-]")
_MISSING_CODES: Final = frozenset({"404", "NoSuchKey", "NotFound"})


class R2Unavailable(Exception):  # noqa: N818 - mirrors the API code large_files_unavailable
    """Storage could not be reached or refused the request."""


class ObjectTooLarge(Exception):  # noqa: N818
    """An object exceeded the size it was allowed to have."""


def _client(cfg: R2Config, *, fast: bool = False) -> S3Client:
    """`fast` is for best-effort housekeeping (the sweep): one retry, short timeouts."""
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key.get_secret_value(),
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=3 if fast else 5,
            read_timeout=5 if fast else 30,
            retries={"total_max_attempts": 2 if fast else 3, "mode": "standard"},
            # R2 compatibility: no default CRC headers/params on requests or presigned URLs.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _is_missing(exc: ClientError) -> bool:
    err = exc.response.get("Error", {})
    status = str(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
    return str(err.get("Code", "")) in _MISSING_CODES or status == "404"


def safe_filename(name: str) -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", name).strip("._") or "result"
    return cleaned[:200]


@dataclass(frozen=True)
class UploadKeys:
    """Object-key layout. No original filenames or user data ever appear in keys."""

    root: str  # "<prefix>/<YYYYMMDDHH>/<upload_id>/"

    @classmethod
    def for_upload(cls, prefix: str, upload: UploadId) -> UploadKeys:
        return cls(f"{prefix}/{upload.hour_bucket}/{upload.value}/")

    @property
    def inputs(self) -> str:
        return self.root + "in/"

    def input(self, index: int) -> str:
        return f"{self.inputs}{index:03d}"

    def output(self, ext: str) -> str:
        return f"{self.root}out/result.{ext}"

    @property
    def lock(self) -> str:
        return self.root + "run.lock"


class R2Store:
    """Thin, synchronous wrapper around the S3 API. Call from a worker thread."""

    def __init__(
        self, cfg: R2Config, client: S3Client | None = None, *, fast: bool = False
    ) -> None:
        self.cfg = cfg
        self.bucket = cfg.bucket
        self._s3 = client if client is not None else _client(cfg, fast=fast)

    # ---------------------------------------------------------------- presign
    def presign_put(self, key: str, content_type: str, size: int, expires: int) -> str:
        """Presigned PUT with Content-Type AND Content-Length in the signed headers, so the
        upload must be exactly `size` bytes of the declared type."""
        try:
            return str(
                self._s3.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self.bucket,
                        "Key": key,
                        "ContentType": content_type,
                        "ContentLength": size,
                    },
                    ExpiresIn=expires,
                    HttpMethod="PUT",
                )
            )
        except (BotoCoreError, ClientError) as e:
            raise R2Unavailable(type(e).__name__) from None

    def presign_get(self, key: str, filename: str, media_type: str, expires: int) -> str:
        try:
            return str(
                self._s3.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self.bucket,
                        "Key": key,
                        "ResponseContentDisposition": (
                            f'attachment; filename="{safe_filename(filename)}"'
                        ),
                        "ResponseContentType": media_type,
                        "ResponseCacheControl": "no-store",
                    },
                    ExpiresIn=expires,
                )
            )
        except (BotoCoreError, ClientError) as e:
            raise R2Unavailable(type(e).__name__) from None

    # ---------------------------------------------------------------- objects
    def head_size(self, key: str) -> int | None:
        """Object size in bytes, or None when it does not exist."""
        try:
            head = self._s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if _is_missing(e):
                return None
            raise R2Unavailable(type(e).__name__) from None
        except BotoCoreError as e:
            raise R2Unavailable(type(e).__name__) from None
        return int(head["ContentLength"])

    def download_bytes(self, key: str, max_bytes: int) -> bytes:
        """Streams an object into one buffer in chunks, failing as soon as it passes
        `max_bytes` (no disk round trip, no second copy)."""
        buf = bytearray()
        try:
            body = self._s3.get_object(Bucket=self.bucket, Key=key)["Body"]
            try:
                for chunk in body.iter_chunks(_CHUNK):
                    if len(buf) + len(chunk) > max_bytes:
                        raise ObjectTooLarge
                    buf += chunk
            finally:
                body.close()
        except ClientError as e:
            if _is_missing(e):
                raise FileNotFoundError from None
            raise R2Unavailable(type(e).__name__) from None
        except BotoCoreError as e:
            raise R2Unavailable(type(e).__name__) from None
        return bytes(buf)

    def create_once(self, key: str) -> bool:
        """Creates an empty object only if it does not exist yet (S3 conditional write,
        `If-None-Match: *`). Returns False when it already exists."""
        try:
            self._s3.put_object(Bucket=self.bucket, Key=key, Body=b"", IfNoneMatch="*")
        except ClientError as e:
            err = e.response.get("Error", {})
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if err.get("Code") in ("PreconditionFailed", "ConditionalRequestConflict") or (
                status in (409, 412)
            ):
                return False
            raise R2Unavailable(type(e).__name__) from None
        except BotoCoreError as e:
            raise R2Unavailable(type(e).__name__) from None
        return True

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        except (BotoCoreError, ClientError) as e:
            raise R2Unavailable(type(e).__name__) from None

    def _list_page(self, prefix: str) -> list[str]:
        try:
            page = self._s3.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, MaxKeys=_DELETE_BATCH
            )
        except (BotoCoreError, ClientError) as e:
            raise R2Unavailable(type(e).__name__) from None
        return [obj["Key"] for obj in page.get("Contents", [])]

    def delete_keys(self, keys: Iterable[str], *, within: str | None = None) -> int:
        """Deletes `keys`; every key must lie under `within` (default: the configured
        prefix), otherwise nothing in that batch is deleted (PrefixViolation)."""
        scope = within if within is not None else self.cfg.prefix + "/"
        batch: list[str] = []
        deleted = 0
        for key in keys:
            batch.append(key)
            if len(batch) == _DELETE_BATCH:
                deleted += self._delete_batch(batch, scope)
                batch = []
        if batch:
            deleted += self._delete_batch(batch, scope)
        return deleted

    def _delete_batch(self, keys: list[str], within: str) -> int:
        # The bucket is shared: refuse to delete anything a misbehaving listing returned
        # from outside the expected prefix.
        if not within.startswith(self.cfg.prefix + "/") or not all(
            k.startswith(within) for k in keys
        ):
            raise R2Unavailable("PrefixViolation")
        try:
            resp = self._s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
            )
        except (BotoCoreError, ClientError) as e:
            raise R2Unavailable(type(e).__name__) from None
        # Quiet mode reports per-key failures in the body instead of raising.
        if resp.get("Errors"):
            raise R2Unavailable("DeleteFailed")
        return len(keys)

    def delete_prefix(self, prefix: str) -> int:
        """Deletes every object under `prefix`, page by page, until the listing is empty."""
        if not prefix.startswith(self.cfg.prefix + "/") or not prefix.endswith("/"):
            raise ValueError("refusing to delete outside the configured prefix")
        deleted = 0
        previous: list[str] | None = None
        while keys := self._list_page(prefix):
            if keys == previous:  # no progress: storage is not honouring deletes
                raise R2Unavailable("DeleteFailed")
            deleted += self._delete_batch(keys, prefix)
            previous = keys
        return deleted

    # ---------------------------------------------------------------- sweep
    def sweep_stale(self, *, now: int, min_age_seconds: int, time_budget: float) -> int:
        """Best-effort: deletes every object under `<prefix>/<hour>/` whose hour bucket
        ended at least `min_age_seconds` ago. Only touches directories named like an hour
        bucket. Stops when the time budget runs out. Never raises."""
        deadline = time.monotonic() + time_budget
        cutoff = hour_bucket(now - min_age_seconds - 3600)  # bucket end <= now - min_age
        root = self.cfg.prefix + "/"
        deleted = 0
        try:
            listing = self._s3.list_objects_v2(
                Bucket=self.bucket, Prefix=root, Delimiter="/", MaxKeys=1000
            )
            hours = sorted(p["Prefix"][len(root) : -1] for p in listing.get("CommonPrefixes", []))
            for hour in hours:
                if time.monotonic() > deadline:
                    break
                if not _HOUR_DIR_RE.fullmatch(hour) or hour > cutoff:
                    continue
                previous: list[str] | None = None
                while time.monotonic() < deadline:
                    keys = self._list_page(f"{root}{hour}/")
                    if not keys or keys == previous:  # done, or no progress
                        break
                    deleted += self._delete_batch(keys, f"{root}{hour}/")
                    previous = keys
        except (BotoCoreError, ClientError, R2Unavailable) as e:
            log.warning("r2_sweep_failed", error_class=type(e).__name__)
        if deleted:
            log.info("r2_sweep_deleted", objects=deleted)
        return deleted

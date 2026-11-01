"""Workspace index (ADR-0002 section 4).

Redis hash ``ws:<job_id>`` (created_at, hour, expires_at, state, delete_after) plus the ZSET
``ws:expiry`` scored by deletion deadline. The index speeds deletion up; correctness never
depends on it (the sweeper also scans storage hour buckets).

``InMemoryWorkspaceIndex`` exists for tests and single-process local runs without Redis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Final, Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

from pdfapp.backend.app.storage.errors import StorageUnavailable

EXPIRY_ZSET: Final = "ws:expiry"
FAILURES_LIST: Final = "ws:cleanup_failures"
ATTEMPTS_HASH: Final = "ws:cleanup_attempts"
FAILURES_KEEP: Final = 1000
FAILURES_TTL_SECONDS: Final = 7 * 24 * 3600
_REQUIRED_FIELDS: Final = frozenset({"job_id", "hour", "created_at", "expires_at", "state"})


@dataclass(frozen=True)
class WorkspaceRecord:
    job_id: str
    hour: str
    created_at: datetime
    expires_at: datetime
    state: str
    delete_after: datetime | None = None
    reason: str | None = None

    @property
    def deadline(self) -> datetime:
        if self.delete_after is not None and self.delete_after < self.expires_at:
            return self.delete_after
        return self.expires_at

    def to_mapping(self) -> dict[str, str]:
        data = {
            "job_id": self.job_id,
            "hour": self.hour,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "state": self.state,
        }
        if self.delete_after is not None:
            data["delete_after"] = self.delete_after.isoformat()
        if self.reason is not None:
            data["reason"] = self.reason
        return data

    @classmethod
    def from_mapping(cls, data: dict[str, str]) -> WorkspaceRecord:
        delete_after = data.get("delete_after")
        return cls(
            job_id=data["job_id"],
            hour=data["hour"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            state=data["state"],
            delete_after=datetime.fromisoformat(delete_after) if delete_after else None,
            reason=data.get("reason"),
        )


class WorkspaceIndex(Protocol):
    async def put(self, record: WorkspaceRecord, *, ttl_seconds: int) -> None: ...
    async def get(self, job_id: str) -> WorkspaceRecord | None: ...
    async def tombstone(self, job_id: str, *, reason: str, ttl_seconds: int) -> None: ...
    async def reschedule(self, job_id: str, deadline: datetime) -> None: ...
    async def due(self, now: datetime, limit: int) -> list[str]: ...
    async def unschedule(self, job_id: str) -> None: ...
    async def record_failure(self, entry: dict[str, Any]) -> int: ...
    async def failures(self, limit: int = 100) -> list[dict[str, Any]]: ...


def _score(moment: datetime) -> float:
    return moment.astimezone(UTC).timestamp()


class RedisWorkspaceIndex:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(job_id: str) -> str:
        return f"ws:{job_id}"

    async def put(self, record: WorkspaceRecord, *, ttl_seconds: int) -> None:
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.delete(self._key(record.job_id))
                # redis-py's stub types the mapping key invariantly; str keys are valid.
                pipe.hset(self._key(record.job_id), mapping=record.to_mapping())  # type: ignore[arg-type]
                pipe.expire(self._key(record.job_id), ttl_seconds)
                pipe.zadd(EXPIRY_ZSET, {record.job_id: _score(record.deadline)})
                await pipe.execute()
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc

    async def get(self, job_id: str) -> WorkspaceRecord | None:
        try:
            raw: dict[bytes | str, bytes | str] = await self._redis.hgetall(self._key(job_id))
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc
        if not raw:
            return None
        data = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in raw.items()
        }
        if not _REQUIRED_FIELDS.issubset(data):
            return None  # bare tombstone left after the full record expired
        return WorkspaceRecord.from_mapping(data)

    async def tombstone(self, job_id: str, *, reason: str, ttl_seconds: int) -> None:
        key = self._key(job_id)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.zrem(EXPIRY_ZSET, job_id)
                if ttl_seconds > 0:
                    pipe.hset(key, mapping={"state": "deleted", "reason": reason})
                    pipe.expire(key, ttl_seconds)
                else:
                    pipe.delete(key)
                await pipe.execute()
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc

    async def reschedule(self, job_id: str, deadline: datetime) -> None:
        try:
            await self._redis.zadd(EXPIRY_ZSET, {job_id: _score(deadline)})
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc

    async def due(self, now: datetime, limit: int) -> list[str]:
        try:
            members = await self._redis.zrangebyscore(
                EXPIRY_ZSET, "-inf", _score(now), start=0, num=limit
            )
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc
        return [m.decode() if isinstance(m, bytes) else str(m) for m in members]

    async def unschedule(self, job_id: str) -> None:
        try:
            await self._redis.zrem(EXPIRY_ZSET, job_id)
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc

    async def record_failure(self, entry: dict[str, Any]) -> int:
        job_id = str(entry["job_id"])
        try:
            attempt = int(await self._redis.hincrby(ATTEMPTS_HASH, job_id, 1))
            payload = json.dumps({**entry, "attempt": attempt}, sort_keys=True)
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.expire(ATTEMPTS_HASH, FAILURES_TTL_SECONDS)
                pipe.lpush(FAILURES_LIST, payload)
                pipe.ltrim(FAILURES_LIST, 0, FAILURES_KEEP - 1)
                pipe.expire(FAILURES_LIST, FAILURES_TTL_SECONDS)
                await pipe.execute()
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc
        return attempt

    async def failures(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            raw = await self._redis.lrange(FAILURES_LIST, 0, limit - 1)
        except RedisError as exc:
            raise StorageUnavailable("index unavailable") from exc
        return [json.loads(item) for item in raw]


class InMemoryWorkspaceIndex:
    """Process-local index. Not shared between api and workers: tests and local only."""

    def __init__(self) -> None:
        self._records: dict[str, WorkspaceRecord] = {}
        self._schedule: dict[str, float] = {}
        self._failures: list[dict[str, Any]] = []
        self._attempts: dict[str, int] = {}

    async def put(self, record: WorkspaceRecord, *, ttl_seconds: int) -> None:
        self._records[record.job_id] = record
        self._schedule[record.job_id] = _score(record.deadline)

    async def get(self, job_id: str) -> WorkspaceRecord | None:
        return self._records.get(job_id)

    async def tombstone(self, job_id: str, *, reason: str, ttl_seconds: int) -> None:
        self._schedule.pop(job_id, None)
        record = self._records.get(job_id)
        if record is None or ttl_seconds <= 0:
            self._records.pop(job_id, None)
            return
        self._records[job_id] = replace(record, state="deleted", reason=reason)

    async def reschedule(self, job_id: str, deadline: datetime) -> None:
        self._schedule[job_id] = _score(deadline)

    async def due(self, now: datetime, limit: int) -> list[str]:
        cutoff = _score(now)
        ordered = sorted(self._schedule.items(), key=lambda item: item[1])
        return [job_id for job_id, score in ordered if score <= cutoff][:limit]

    async def unschedule(self, job_id: str) -> None:
        self._schedule.pop(job_id, None)

    async def record_failure(self, entry: dict[str, Any]) -> int:
        job_id = str(entry["job_id"])
        attempt = self._attempts.get(job_id, 0) + 1
        self._attempts[job_id] = attempt
        self._failures.insert(0, {**entry, "attempt": attempt})
        del self._failures[FAILURES_KEEP:]
        return attempt

    async def failures(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self._failures[:limit])

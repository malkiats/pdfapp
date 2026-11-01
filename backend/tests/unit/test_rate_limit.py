from __future__ import annotations

import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from pdfapp.backend.app.middleware.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    client_ip,
    hash_client,
)


class FakeTime:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


async def test_in_memory_fixed_window() -> None:
    clock = FakeTime(1_000_000.0)
    limiter = InMemoryRateLimiter(3, 60, clock=clock)
    results = [await limiter.hit("k") for _ in range(4)]
    assert [r.allowed for r in results] == [True, True, True, False]
    assert [r.remaining for r in results] == [2, 1, 0, 0]
    assert 1 <= results[-1].reset_seconds <= 60
    assert (await limiter.hit("other")).allowed  # keys are independent
    clock.now += 60
    assert (await limiter.hit("k")).allowed  # new window


async def test_redis_limiter_counts_in_redis() -> None:
    redis = fakeredis.FakeAsyncRedis()
    clock = FakeTime(1_000_000.0)
    limiter = RedisRateLimiter(redis, 2, 60, clock=clock)
    assert (await limiter.hit("k")).allowed
    assert (await limiter.hit("k")).allowed
    denied = await limiter.hit("k")
    assert not denied.allowed
    keys = [k.decode() for k in await redis.keys("rl:anon:*")]
    assert keys == [f"rl:anon:k:{1_000_000 // 60}"]
    assert 0 < await redis.ttl(keys[0]) <= 61
    # A second limiter instance (another API replica) shares the same counters.
    other = RedisRateLimiter(redis, 2, 60, clock=clock)
    assert not (await other.hit("k")).allowed


async def test_redis_failure_falls_back_to_memory() -> None:
    class DownRedis(fakeredis.FakeAsyncRedis):
        def pipeline(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def,override]
            raise RedisConnectionError("redis://user:CANARY@host down")

    fallback = InMemoryRateLimiter(1, 60)
    limiter = RedisRateLimiter(DownRedis(), 1, 60, fallback=fallback)
    assert (await limiter.hit("k")).allowed
    assert not (await limiter.hit("k")).allowed


@pytest.mark.parametrize(
    ("hops", "xff", "expected"),
    [
        (0, "1.1.1.1", "10.0.0.9"),
        (1, "1.1.1.1, 2.2.2.2", "2.2.2.2"),
        (2, "spoofed, 1.1.1.1, 2.2.2.2", "1.1.1.1"),
        (1, None, "10.0.0.9"),
        (3, "1.1.1.1", "1.1.1.1"),
    ],
)
def test_client_ip_respects_trusted_hops(hops: int, xff: str | None, expected: str) -> None:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    scope = {"type": "http", "client": ("10.0.0.9", 1234), "headers": headers}
    assert client_ip(scope, hops) == expected


def test_ip_is_hashed_with_key() -> None:
    a = hash_client("203.0.113.7", b"k1" * 16)
    assert "203.0.113.7" not in a
    assert len(a) == 32
    assert a != hash_client("203.0.113.7", b"k2" * 16)
    assert a == hash_client("203.0.113.7", b"k1" * 16)

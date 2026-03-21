"""Tests for the token bucket rate limiter (T2.3).

All tests run in fast mode with mocked asyncio.sleep to avoid real delays.
Redis is not required — all tests use cache=None (in-process fallback).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from piea.modules.username.rate_limiter import (
    _INITIAL_BACKOFF_SECONDS,
    _MAX_BACKOFF_SECONDS,
    RateLimiterFactory,
    TokenBucketRateLimiter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_limiter(rpm: int = 60) -> TokenBucketRateLimiter:
    return TokenBucketRateLimiter(
        platform="TestSite", requests_per_minute=rpm, cache=None
    )


# ---------------------------------------------------------------------------
# Token bucket — basic behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_succeeds_when_bucket_has_tokens() -> None:
    limiter = _make_limiter(rpm=60)
    # Bucket starts full; first acquire should not block
    with patch(
        "piea.modules.username.rate_limiter.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        await limiter.acquire()
    # Should have slept once (the mandatory inter-request cooldown in finally)
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_acquire_calls_sleep_for_cooldown() -> None:
    limiter = _make_limiter(rpm=60)
    with patch(
        "piea.modules.username.rate_limiter.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        await limiter.acquire()
    # Mandatory cooldown sleep = 1 / refill_rate = 1 second for 60 rpm
    assert mock_sleep.called
    sleep_duration = mock_sleep.call_args[0][0]
    assert sleep_duration == pytest.approx(1.0, rel=0.05)


@pytest.mark.asyncio
async def test_tokens_decrease_after_acquire() -> None:
    limiter = _make_limiter(rpm=60)
    initial_tokens = limiter._tokens
    with patch(
        "piea.modules.username.rate_limiter.asyncio.sleep", new_callable=AsyncMock
    ):
        await limiter.acquire()
    assert limiter._tokens < initial_tokens


@pytest.mark.asyncio
async def test_acquire_multiple_times_depletes_tokens() -> None:
    limiter = _make_limiter(rpm=3)  # tiny bucket
    with patch(
        "piea.modules.username.rate_limiter.asyncio.sleep", new_callable=AsyncMock
    ):
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
    assert limiter._tokens < 1.0


# ---------------------------------------------------------------------------
# 429 backoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_429_sets_backoff_deadline() -> None:
    limiter = _make_limiter()
    import time

    before = time.monotonic()
    await limiter.record_429(retry_after=10.0)
    assert limiter._backoff_until >= before + 9.9


@pytest.mark.asyncio
async def test_record_429_uses_initial_backoff_when_no_retry_after() -> None:
    limiter = _make_limiter()
    await limiter.record_429(retry_after=None)
    import time

    assert limiter._backoff_until >= time.monotonic() + _INITIAL_BACKOFF_SECONDS - 0.1


@pytest.mark.asyncio
async def test_record_429_caps_at_max_backoff() -> None:
    limiter = _make_limiter()
    await limiter.record_429(retry_after=_MAX_BACKOFF_SECONDS + 100)
    import time

    remaining = limiter._backoff_until - time.monotonic()
    assert remaining <= _MAX_BACKOFF_SECONDS + 1.0


@pytest.mark.asyncio
async def test_acquire_respects_backoff_delay() -> None:
    limiter = _make_limiter()
    await limiter.record_429(retry_after=5.0)
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    with patch(
        "piea.modules.username.rate_limiter.asyncio.sleep", side_effect=fake_sleep
    ):
        await limiter.acquire()

    # The first sleep call should be the backoff sleep
    assert any(s >= 4.9 for s in sleep_calls), (
        f"Expected a >= 5s sleep, got: {sleep_calls}"
    )


# ---------------------------------------------------------------------------
# RateLimiterFactory
# ---------------------------------------------------------------------------


def test_factory_returns_same_instance_for_same_key() -> None:
    factory = RateLimiterFactory(cache=None)
    a = factory.get("GitHub", 60)
    b = factory.get("GitHub", 60)
    assert a is b


def test_factory_returns_different_instances_for_different_platforms() -> None:
    factory = RateLimiterFactory(cache=None)
    github = factory.get("GitHub", 60)
    twitter = factory.get("Twitter", 15)
    assert github is not twitter


def test_factory_returns_different_instances_for_different_rpms() -> None:
    factory = RateLimiterFactory(cache=None)
    a = factory.get("GitHub", 60)
    b = factory.get("GitHub", 30)
    assert a is not b


def test_factory_uses_none_cache_for_in_process_fallback() -> None:
    factory = RateLimiterFactory(cache=None)
    limiter = factory.get("TestSite", 30)
    assert limiter._cache is None

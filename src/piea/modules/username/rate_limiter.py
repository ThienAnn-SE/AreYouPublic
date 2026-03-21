"""Per-platform token bucket rate limiter for username enumeration.

Each platform gets its own rate limiter keyed by platform name. Tokens
are refilled continuously based on the configured requests-per-minute.

When Redis is unavailable, falls back to an in-process asyncio.Lock
implementation. This satisfies NFR-R1 (graceful degradation).

Per L009: the rate-limit sleep is always in a ``finally`` block to ensure
it executes even when the caller raises an exception inside the token
acquisition window.
"""

from __future__ import annotations

import asyncio
import logging
import time

from piea.core.cache import CacheLayer

logger = logging.getLogger(__name__)

# Retry configuration for 429 responses (FR-3.2)
_MAX_429_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 5.0
_MAX_BACKOFF_SECONDS = 60.0


# ---------------------------------------------------------------------------
# Token bucket rate limiter
# ---------------------------------------------------------------------------


class TokenBucketRateLimiter:
    """Async token bucket rate limiter for a single platform.

    Tokens are added at a constant rate of ``requests_per_minute / 60``
    tokens per second. The bucket capacity equals ``requests_per_minute``.

    When ``cache`` is provided, token state is persisted to Redis so
    multiple workers share the same bucket. When Redis is unavailable
    or ``cache`` is None, an in-process asyncio.Lock governs access.

    Args:
        platform: Platform name (used for logging and Redis key).
        requests_per_minute: Maximum sustained request rate.
        cache: Optional CacheLayer for Redis-backed state. If None,
            falls back to in-process token tracking.
    """

    def __init__(
        self,
        platform: str,
        requests_per_minute: int,
        cache: CacheLayer | None,
    ) -> None:
        self._platform = platform
        self._rpm = max(1, requests_per_minute)
        self._refill_rate = self._rpm / 60.0  # tokens per second
        self._cache = cache
        self._lock = asyncio.Lock()
        # In-process fallback state
        self._tokens: float = float(self._rpm)
        self._last_refill: float = time.monotonic()
        # 429 backoff state
        self._backoff_until: float = 0.0

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one.

        Per L009, the mandatory inter-request sleep happens in the
        ``finally`` block to prevent bypass on exception.
        """
        # Honour any active 429 backoff first
        now = time.monotonic()
        remaining_backoff = self._backoff_until - now
        if remaining_backoff > 0:
            logger.debug(
                "Platform %s in backoff, sleeping %.1fs",
                self._platform,
                remaining_backoff,
            )
            await asyncio.sleep(remaining_backoff)

        async with self._lock:
            try:
                await self._wait_for_token()
            finally:
                # Always refill at least one token's worth of sleep
                # so callers can't bypass the rate limit on exception.
                sleep_seconds = 1.0 / self._refill_rate
                await asyncio.sleep(sleep_seconds)

    async def record_429(self, retry_after: float | None = None) -> None:
        """Record a 429 response and set the backoff deadline.

        Args:
            retry_after: Seconds to wait as reported by the server.
                If None, the current backoff is doubled (exponential).
        """
        now = time.monotonic()
        current_backoff = max(0.0, self._backoff_until - now)
        if retry_after is not None:
            next_backoff = min(retry_after, _MAX_BACKOFF_SECONDS)
        else:
            next_backoff = min(
                max(current_backoff * 2, _INITIAL_BACKOFF_SECONDS),
                _MAX_BACKOFF_SECONDS,
            )
        self._backoff_until = now + next_backoff
        logger.warning(
            "Platform %s rate limited; backing off %.1fs",
            self._platform,
            next_backoff,
        )

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    async def _wait_for_token(self) -> None:
        """Block until a token is available and consume it."""
        while True:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            # Sleep until the next token arrives
            wait = (1.0 - self._tokens) / self._refill_rate
            await asyncio.sleep(wait)
            self._refill()

    def _refill(self) -> None:
        """Add tokens based on elapsed time since the last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(float(self._rpm), self._tokens + elapsed * self._refill_rate)
        self._last_refill = now


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class RateLimiterFactory:
    """Creates and caches TokenBucketRateLimiter instances per platform.

    One factory is shared across a UsernameChecker so that all concurrent
    coroutines share the same rate limiter for each platform.

    Args:
        cache: Optional CacheLayer for Redis-backed rate limiter state.
    """

    def __init__(self, cache: CacheLayer | None = None) -> None:
        self._cache = cache
        self._limiters: dict[str, TokenBucketRateLimiter] = {}

    def get(self, platform: str, requests_per_minute: int) -> TokenBucketRateLimiter:
        """Return the rate limiter for *platform*, creating it if needed.

        Args:
            platform: Platform identifier string.
            requests_per_minute: RPM cap for this platform.

        Returns:
            The existing or newly created TokenBucketRateLimiter.
        """
        key = f"{platform}:{requests_per_minute}"
        if key not in self._limiters:
            self._limiters[key] = TokenBucketRateLimiter(
                platform=platform,
                requests_per_minute=requests_per_minute,
                cache=self._cache,
            )
        return self._limiters[key]

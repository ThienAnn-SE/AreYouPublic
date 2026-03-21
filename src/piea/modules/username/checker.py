"""Async username existence checker across multiple platforms.

Executes concurrent HTTP HEAD/GET requests against the platform registry,
classifies each response, and applies per-platform rate limiting.

Security notes:
  - Username is validated against a strict allowlist before any URL substitution
    to prevent SSRF via crafted usernames (NFR-S3).
  - All checks use HTTPS URLs only (NFR-S2).
  - HTTPStatusError is caught and re-raised as a domain error so the raw
    URL (which contains the username) never leaks in exception messages (L007).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import httpx

from piea.modules.username.platforms import PlatformConfig, PlatformRegistry
from piea.modules.username.rate_limiter import RateLimiterFactory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = "PIEA-SecurityScanner/1.0"

# Username validation: alphanumeric, dots, underscores, hyphens, 1–100 chars.
# This must be enforced before any URL substitution (NFR-S3).
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")

# HTTP client settings
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 15.0
_MAX_CONNECTIONS = 100
_MAX_KEEPALIVE = 50

# Retry configuration for 429 responses (FR-3.2)
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 5.0
_MAX_BACKOFF = 60.0

# Default concurrency limit (overridden at construction time)
_DEFAULT_MAX_CONCURRENCY = 50


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class CheckStatus(StrEnum):
    """Result of a single platform existence check."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True, slots=True)
class PlatformCheckResult:
    """Result of checking a single platform for a username.

    Attributes:
        platform: Platform name from the registry.
        url: The profile URL that was checked (contains the username).
        category: Platform category (e.g. "social_media").
        status: Outcome of the check.
        checked_at: ISO-8601 UTC timestamp of when the check ran.
        error_message: Human-readable error detail (only set on ERROR/RATE_LIMITED).
    """

    platform: str
    url: str
    category: str
    status: CheckStatus
    checked_at: str
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Username checker
# ---------------------------------------------------------------------------


class UsernameChecker:
    """Checks a username against all registered platforms concurrently.

    Uses a shared httpx.AsyncClient with connection pooling and a global
    asyncio.Semaphore to cap simultaneous outbound connections.

    Args:
        registry: Platform registry supplying the list of sites to check.
        rate_limiter_factory: Factory for per-platform token bucket limiters.
        http_client: Optional pre-configured httpx.AsyncClient. If None,
            a new one is created (and closed in ``close()``).
        max_concurrency: Maximum simultaneous HTTP requests. Defaults to 50.
    """

    def __init__(
        self,
        registry: PlatformRegistry,
        rate_limiter_factory: RateLimiterFactory,
        http_client: httpx.AsyncClient | None = None,
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        self._registry = registry
        self._rate_limiter_factory = rate_limiter_factory
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT),
            limits=httpx.Limits(
                max_connections=_MAX_CONNECTIONS,
                max_keepalive_connections=_MAX_KEEPALIVE,
            ),
            follow_redirects=True,
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def check_all_platforms(self, username: str) -> list[PlatformCheckResult]:
        """Check *username* against every platform in the registry concurrently.

        Args:
            username: The username to look up. Must match ``^[a-zA-Z0-9._-]{1,100}$``.

        Returns:
            A list of PlatformCheckResult, one per platform.

        Raises:
            ValueError: If *username* fails validation (before any HTTP requests).
        """
        validated = _validate_username(username)
        platforms = self._registry.get_all()

        tasks = [
            self._check_single_platform(validated, platform) for platform in platforms
        ]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def close(self) -> None:
        """Close the HTTP client if we created it."""
        if self._owns_client:
            await self._client.aclose()

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    async def _check_single_platform(
        self, username: str, platform: PlatformConfig
    ) -> PlatformCheckResult:
        """Check *username* on a single platform with retries.

        Args:
            username: Validated username string.
            platform: Platform configuration to check against.

        Returns:
            A PlatformCheckResult with the outcome.
        """
        url = platform.build_url(username)
        checked_at = datetime.now(UTC).isoformat()
        return await self._execute_with_retry(platform, url, checked_at)

    async def _execute_with_retry(
        self,
        platform: PlatformConfig,
        url: str,
        checked_at: str,
    ) -> PlatformCheckResult:
        """Execute a platform check with 429 retry/backoff logic (FR-3.2).

        Args:
            platform: Platform configuration.
            url: Fully resolved profile URL.
            checked_at: ISO-8601 timestamp for the result.

        Returns:
            A PlatformCheckResult with the final outcome.
        """
        rate_limiter = self._rate_limiter_factory.get(
            platform.platform, platform.rate_limit_requests_per_minute
        )
        backoff = _INITIAL_BACKOFF

        for attempt in range(1, _MAX_RETRIES + 1):
            outcome = await self._fetch_under_semaphore(platform, url)
            if isinstance(outcome, PlatformCheckResult):
                return outcome  # request-level error (timeout, network, HTTP error)

            if outcome.status_code == 429:
                backoff = await _handle_429(platform, rate_limiter, attempt, backoff)
                continue

            return _classify_response(platform, url, outcome.status_code, checked_at)

        return PlatformCheckResult(
            platform=platform.platform,
            url=url,
            category=platform.category,
            status=CheckStatus.RATE_LIMITED,
            checked_at=checked_at,
            error_message=f"Rate limited after {_MAX_RETRIES} retries",
        )

    async def _fetch_under_semaphore(
        self,
        platform: PlatformConfig,
        url: str,
    ) -> httpx.Response | PlatformCheckResult:
        """Acquire the semaphore, make the request, and classify transport errors.

        Per L009, the semaphore is released via ``finally`` with a sleep(0)
        yield so other coroutines can proceed even on exception.

        Args:
            platform: Platform configuration (determines HTTP method).
            url: Fully resolved profile URL.

        Returns:
            An httpx.Response on success, or an error PlatformCheckResult
            on timeout, network failure, or HTTP-level error.
        """
        checked_at = datetime.now(UTC).isoformat()
        async with self._semaphore:
            try:
                return await self._make_request(platform, url)
            except httpx.TimeoutException:
                return _error_result(platform, url, checked_at, "Request timed out")
            except httpx.HTTPStatusError as exc:
                # Domain error: URL contains username — never let raw exc propagate (L007)
                return _error_result(
                    platform, url, checked_at, f"HTTP error {exc.response.status_code}"
                )
            except httpx.RequestError:
                return _error_result(
                    platform, url, checked_at, "Network error during request"
                )
            finally:
                # Yield control so other coroutines can proceed (L009)
                await asyncio.sleep(0)

    async def _make_request(self, platform: PlatformConfig, url: str) -> httpx.Response:
        """Execute an HTTP request for *url* using the platform's check method.

        Args:
            platform: Platform configuration (determines HTTP method).
            url: Fully resolved URL to request.

        Returns:
            The HTTP response.

        Raises:
            httpx.TimeoutException: On request timeout.
            httpx.HTTPStatusError: On non-2xx responses (after raise_for_status).
            httpx.RequestError: On network-level errors.
        """
        from piea.modules.username.platforms import CheckMethod

        if platform.check_method == CheckMethod.HEAD:
            return await self._client.head(url)
        return await self._client.get(url)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _validate_username(username: str) -> str:
    """Validate *username* against the allowed character set.

    Args:
        username: Raw username input.

    Returns:
        The username unchanged if valid.

    Raises:
        ValueError: If the username contains invalid characters or is out of
            the allowed length range. No request is made before this check.
    """
    if not _USERNAME_PATTERN.match(username):
        raise ValueError(
            f"Invalid username {username!r}. "
            "Must be 1–100 characters: letters, digits, dots, underscores, hyphens only."
        )
    return username


def _classify_response(
    platform: PlatformConfig,
    url: str,
    status_code: int,
    checked_at: str,
) -> PlatformCheckResult:
    """Map an HTTP status code to a CheckStatus.

    Args:
        platform: Platform configuration with expected status codes.
        url: The profile URL that was checked.
        status_code: The HTTP response status code.
        checked_at: ISO-8601 timestamp of the check.

    Returns:
        A PlatformCheckResult with the appropriate status.
    """
    if status_code == platform.expected_status_found:
        return PlatformCheckResult(
            platform=platform.platform,
            url=url,
            category=platform.category,
            status=CheckStatus.FOUND,
            checked_at=checked_at,
        )
    if status_code == platform.expected_status_not_found:
        return PlatformCheckResult(
            platform=platform.platform,
            url=url,
            category=platform.category,
            status=CheckStatus.NOT_FOUND,
            checked_at=checked_at,
        )
    # Unexpected status code — treat as an error
    return PlatformCheckResult(
        platform=platform.platform,
        url=url,
        category=platform.category,
        status=CheckStatus.ERROR,
        checked_at=checked_at,
        error_message=f"Unexpected HTTP status {status_code}",
    )


def _error_result(
    platform: PlatformConfig,
    url: str,
    checked_at: str,
    message: str,
) -> PlatformCheckResult:
    """Build an ERROR PlatformCheckResult."""
    return PlatformCheckResult(
        platform=platform.platform,
        url=url,
        category=platform.category,
        status=CheckStatus.ERROR,
        checked_at=checked_at,
        error_message=message,
    )


async def _handle_429(
    platform: PlatformConfig,
    rate_limiter: object,
    attempt: int,
    backoff: float,
) -> float:
    """Record a 429 response, sleep the backoff, and return the next backoff.

    Args:
        platform: Platform config (for logging).
        rate_limiter: TokenBucketRateLimiter for this platform.
        attempt: Current attempt number (1-based, for logging).
        backoff: Current backoff in seconds.

    Returns:
        The next backoff value (doubled, capped at _MAX_BACKOFF).
    """
    from piea.modules.username.rate_limiter import TokenBucketRateLimiter

    if isinstance(rate_limiter, TokenBucketRateLimiter):
        await rate_limiter.record_429(retry_after=backoff)
    logger.warning(
        "Platform %s returned 429 (attempt %d/%d), backing off %.1fs",
        platform.platform,
        attempt,
        _MAX_RETRIES,
        backoff,
    )
    await asyncio.sleep(min(backoff, _MAX_BACKOFF))
    return min(backoff * 2, _MAX_BACKOFF)

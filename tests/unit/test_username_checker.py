"""Tests for the async username checker (T2.2).

Uses respx to mock httpx responses — no real HTTP calls are made.
Tests verify concurrent execution, status classification, error handling,
rate-limit retries, and username validation (NFR-S3).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from piea.modules.username.checker import (
    CheckStatus,
    UsernameChecker,
    _classify_response,
    _validate_username,
)
from piea.modules.username.platforms import PlatformConfig, PlatformRegistry
from piea.modules.username.rate_limiter import RateLimiterFactory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_platform(
    name: str = "TestSite",
    url_pattern: str = "https://testsite.example/{username}",
    found: int = 200,
    not_found: int = 404,
    category: str = "test",
    rpm: int = 60,
) -> PlatformConfig:
    from piea.modules.username.platforms import CheckMethod

    return PlatformConfig(
        platform=name,
        url_pattern=url_pattern,
        expected_status_found=found,
        expected_status_not_found=not_found,
        category=category,
        has_public_api=False,
        rate_limit_requests_per_minute=rpm,
        check_method=CheckMethod.GET,
    )


def _make_registry(*platforms: PlatformConfig) -> PlatformRegistry:
    """Build a registry pre-loaded with the given platforms."""
    registry = PlatformRegistry.__new__(PlatformRegistry)
    registry._platforms = list(platforms)
    registry._loaded = True
    registry._config_path = Path("/fake/path.json")
    return registry


def _make_checker(
    *platforms: PlatformConfig,
    http_client: httpx.AsyncClient | None = None,
) -> UsernameChecker:
    registry = _make_registry(*platforms)
    factory = RateLimiterFactory(cache=None)
    client = http_client or httpx.AsyncClient()
    return UsernameChecker(
        registry=registry,
        rate_limiter_factory=factory,
        http_client=client,
        max_concurrency=10,
    )


# ---------------------------------------------------------------------------
# Username validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "username",
    ["alice", "bob123", "user.name", "user-name", "user_name", "a" * 100],
)
def test_valid_usernames_pass_validation(username: str) -> None:
    assert _validate_username(username) == username


@pytest.mark.parametrize(
    "username",
    ["", "../evil", "user name", "a" * 101, "user@site", "<script>", "user/path"],
)
def test_invalid_usernames_raise_value_error(username: str) -> None:
    with pytest.raises(ValueError, match="Invalid username"):
        _validate_username(username)


@pytest.mark.asyncio
async def test_invalid_username_raises_before_any_http_request() -> None:
    platform = _make_platform()
    checker = _make_checker(platform)
    with respx.mock:
        with pytest.raises(ValueError):
            await checker.check_all_platforms("../evil")
    await checker.close()


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------


def test_classify_200_as_found() -> None:
    platform = _make_platform(found=200, not_found=404)
    result = _classify_response(
        platform, "https://testsite.example/alice", 200, "2026-01-01T00:00:00+00:00"
    )
    assert result.status == CheckStatus.FOUND


def test_classify_404_as_not_found() -> None:
    platform = _make_platform(found=200, not_found=404)
    result = _classify_response(
        platform, "https://testsite.example/alice", 404, "2026-01-01T00:00:00+00:00"
    )
    assert result.status == CheckStatus.NOT_FOUND


def test_classify_unexpected_status_as_error() -> None:
    platform = _make_platform(found=200, not_found=404)
    result = _classify_response(
        platform, "https://testsite.example/alice", 403, "2026-01-01T00:00:00+00:00"
    )
    assert result.status == CheckStatus.ERROR
    assert "403" in (result.error_message or "")


# ---------------------------------------------------------------------------
# Concurrent checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_all_platforms_returns_one_result_per_platform() -> None:
    platforms = [
        _make_platform("Site1", "https://site1.example/{username}"),
        _make_platform("Site2", "https://site2.example/{username}"),
        _make_platform("Site3", "https://site3.example/{username}"),
    ]
    with respx.mock:
        respx.get("https://site1.example/testuser").mock(
            return_value=httpx.Response(200)
        )
        respx.get("https://site2.example/testuser").mock(
            return_value=httpx.Response(404)
        )
        respx.get("https://site3.example/testuser").mock(
            return_value=httpx.Response(200)
        )

        checker = _make_checker(*platforms)
        results = await checker.check_all_platforms("testuser")
        await checker.close()

    assert len(results) == 3
    statuses = {r.platform: r.status for r in results}
    assert statuses["Site1"] == CheckStatus.FOUND
    assert statuses["Site2"] == CheckStatus.NOT_FOUND
    assert statuses["Site3"] == CheckStatus.FOUND


@pytest.mark.asyncio
async def test_found_result_contains_correct_url() -> None:
    platform = _make_platform("MySite", "https://mysite.example/{username}")
    with respx.mock:
        respx.get("https://mysite.example/alice").mock(return_value=httpx.Response(200))
        checker = _make_checker(platform)
        results = await checker.check_all_platforms("alice")
        await checker.close()

    assert results[0].url == "https://mysite.example/alice"
    assert results[0].platform == "MySite"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_returns_error_status() -> None:
    platform = _make_platform("SlowSite", "https://slow.example/{username}")
    with respx.mock:
        respx.get("https://slow.example/testuser").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        checker = _make_checker(platform)
        results = await checker.check_all_platforms("testuser")
        await checker.close()

    assert results[0].status == CheckStatus.ERROR
    assert "timed out" in (results[0].error_message or "").lower()


@pytest.mark.asyncio
async def test_network_error_returns_error_status() -> None:
    platform = _make_platform("BrokenSite", "https://broken.example/{username}")
    with respx.mock:
        respx.get("https://broken.example/testuser").mock(
            side_effect=httpx.ConnectError("refused")
        )
        checker = _make_checker(platform)
        results = await checker.check_all_platforms("testuser")
        await checker.close()

    assert results[0].status == CheckStatus.ERROR


# ---------------------------------------------------------------------------
# 429 rate-limit retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_exhausts_retries_and_returns_rate_limited() -> None:
    platform = _make_platform("ThrottledSite", "https://throttled.example/{username}")

    with respx.mock:
        # Always return 429
        respx.get("https://throttled.example/testuser").mock(
            return_value=httpx.Response(429)
        )
        with patch(
            "piea.modules.username.checker.asyncio.sleep", new_callable=AsyncMock
        ):
            checker = _make_checker(platform)
            results = await checker.check_all_platforms("testuser")
            await checker.close()

    assert results[0].status == CheckStatus.RATE_LIMITED
    assert "retries" in (results[0].error_message or "").lower()


@pytest.mark.asyncio
async def test_429_retry_succeeds_on_second_attempt() -> None:
    platform = _make_platform("RetryOk", "https://retryok.example/{username}")

    responses = [httpx.Response(429), httpx.Response(200)]

    with respx.mock:
        respx.get("https://retryok.example/testuser").mock(side_effect=responses)
        with patch(
            "piea.modules.username.checker.asyncio.sleep", new_callable=AsyncMock
        ):
            checker = _make_checker(platform)
            results = await checker.check_all_platforms("testuser")
            await checker.close()

    assert results[0].status == CheckStatus.FOUND


# ---------------------------------------------------------------------------
# Checker close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_calls_aclose_on_owned_client() -> None:
    platform = _make_platform()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=httpx.Response(200))
    mock_client.aclose = AsyncMock()

    checker = _make_checker(platform, http_client=mock_client)
    checker._owns_client = True  # force ownership
    await checker.close()

    mock_client.aclose.assert_called_once()

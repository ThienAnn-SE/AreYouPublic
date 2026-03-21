"""Tests for UsernameModule (T2.4).

Verifies the BaseModule interface compliance, graceful degradation (NFR-R1),
and correct translation from PlatformCheckResult to ModuleFinding.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from piea.modules.base import ModuleResult, ScanInputs
from piea.modules.username.checker import (
    CheckStatus,
    PlatformCheckResult,
    UsernameChecker,
)
from piea.modules.username.module import UsernameModule, _result_to_finding
from piea.modules.username.platforms import PlatformRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_result(
    platform: str = "GitHub",
    url: str = "https://github.com/testuser",
    category: str = "development",
    status: CheckStatus = CheckStatus.FOUND,
    error_message: str | None = None,
) -> PlatformCheckResult:
    return PlatformCheckResult(
        platform=platform,
        url=url,
        category=category,
        status=status,
        checked_at="2026-01-01T00:00:00+00:00",
        error_message=error_message,
    )


def _make_module(check_results: list[PlatformCheckResult]) -> UsernameModule:
    """Build a UsernameModule with a mocked checker returning *check_results*."""
    mock_checker = AsyncMock(spec=UsernameChecker)
    mock_checker.check_all_platforms.return_value = check_results

    registry = MagicMock(spec=PlatformRegistry)
    module = UsernameModule(checker=mock_checker, registry=registry)
    return module


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------


def test_module_name_is_username_enum() -> None:
    module = _make_module([])
    assert module.name == "username_enum"


# ---------------------------------------------------------------------------
# Missing username (NFR-R1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_with_no_username_returns_failure() -> None:
    module = _make_module([])
    result = await module.execute(ScanInputs(username=None))

    assert isinstance(result, ModuleResult)
    assert result.success is False
    assert result.module_name == "username_enum"
    assert len(result.errors) == 1
    assert "username" in result.errors[0].lower()


@pytest.mark.asyncio
async def test_execute_with_empty_username_returns_failure() -> None:
    module = _make_module([])
    result = await module.execute(ScanInputs(username=""))
    assert result.success is False


# ---------------------------------------------------------------------------
# Successful execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_returns_finding_for_each_found_platform() -> None:
    results = [
        _make_result("GitHub", status=CheckStatus.FOUND),
        _make_result(
            "GitLab", url="https://gitlab.com/testuser", status=CheckStatus.FOUND
        ),
        _make_result(
            "Twitter", url="https://twitter.com/testuser", status=CheckStatus.NOT_FOUND
        ),
    ]
    module = _make_module(results)
    module_result = await module.execute(ScanInputs(username="testuser"))

    assert module_result.success is True
    assert len(module_result.findings) == 2  # only FOUND results
    platforms = {f.platform for f in module_result.findings}
    assert "GitHub" in platforms
    assert "GitLab" in platforms


@pytest.mark.asyncio
async def test_execute_finding_type_is_username_found() -> None:
    results = [_make_result(status=CheckStatus.FOUND)]
    module = _make_module(results)
    module_result = await module.execute(ScanInputs(username="testuser"))

    assert module_result.findings[0].finding_type == "username_found"


@pytest.mark.asyncio
async def test_execute_finding_category_is_username() -> None:
    results = [_make_result(status=CheckStatus.FOUND)]
    module = _make_module(results)
    module_result = await module.execute(ScanInputs(username="testuser"))

    assert module_result.findings[0].category == "username"


@pytest.mark.asyncio
async def test_execute_finding_evidence_contains_url_and_platform() -> None:
    results = [
        _make_result("GitHub", url="https://github.com/alice", status=CheckStatus.FOUND)
    ]
    module = _make_module(results)
    module_result = await module.execute(ScanInputs(username="alice"))

    evidence = module_result.findings[0].evidence
    assert evidence["platform"] == "GitHub"
    assert evidence["url"] == "https://github.com/alice"


@pytest.mark.asyncio
async def test_execute_metadata_includes_platform_counts() -> None:
    results = [
        _make_result(status=CheckStatus.FOUND),
        _make_result("Twitter", status=CheckStatus.NOT_FOUND),
        _make_result("BrokenSite", status=CheckStatus.ERROR, error_message="timeout"),
    ]
    module = _make_module(results)
    module_result = await module.execute(ScanInputs(username="testuser"))

    meta = module_result.metadata
    assert meta["platforms_checked"] == 3
    assert meta["platforms_found"] == 1
    assert meta["platforms_not_found"] == 1
    assert meta["platforms_error"] == 1


@pytest.mark.asyncio
async def test_execute_errors_include_error_platform_messages() -> None:
    results = [
        _make_result("BrokenSite", status=CheckStatus.ERROR, error_message="timeout"),
    ]
    module = _make_module(results)
    module_result = await module.execute(ScanInputs(username="testuser"))

    assert module_result.success is True
    assert any("BrokenSite" in e for e in module_result.errors)


@pytest.mark.asyncio
async def test_execute_with_all_not_found_returns_no_findings() -> None:
    results = [
        _make_result("GitHub", status=CheckStatus.NOT_FOUND),
        _make_result("Twitter", status=CheckStatus.NOT_FOUND),
    ]
    module = _make_module(results)
    module_result = await module.execute(ScanInputs(username="testuser"))

    assert module_result.success is True
    assert module_result.findings == []


# ---------------------------------------------------------------------------
# Graceful degradation (NFR-R1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_swallows_checker_exception_and_returns_failure() -> None:
    """An unexpected exception from the checker must not propagate (NFR-R1)."""
    mock_checker = AsyncMock(spec=UsernameChecker)
    mock_checker.check_all_platforms.side_effect = RuntimeError("unexpected boom")
    registry = MagicMock(spec=PlatformRegistry)
    module = UsernameModule(checker=mock_checker, registry=registry)

    result = await module.execute(ScanInputs(username="testuser"))

    assert result.success is False
    assert result.module_name == "username_enum"
    assert any("failed" in e.lower() or "boom" in e.lower() for e in result.errors)


@pytest.mark.asyncio
async def test_execute_invalid_username_returns_failure_not_exception() -> None:
    mock_checker = AsyncMock(spec=UsernameChecker)
    mock_checker.check_all_platforms.side_effect = ValueError("Invalid username")
    registry = MagicMock(spec=PlatformRegistry)
    module = UsernameModule(checker=mock_checker, registry=registry)

    result = await module.execute(ScanInputs(username="../evil"))
    assert result.success is False


# ---------------------------------------------------------------------------
# _result_to_finding helper
# ---------------------------------------------------------------------------


def test_result_to_finding_sets_correct_fields() -> None:
    result = _make_result(
        "GitHub",
        url="https://github.com/alice",
        category="development",
        status=CheckStatus.FOUND,
    )
    finding = _result_to_finding(result)

    assert finding.finding_type == "username_found"
    assert finding.category == "username"
    assert finding.platform == "GitHub"
    assert "GitHub" in finding.title
    assert finding.evidence["url"] == "https://github.com/alice"
    assert finding.evidence["category"] == "development"


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_delegates_to_checker_when_owned() -> None:
    mock_checker = AsyncMock(spec=UsernameChecker)
    registry = MagicMock(spec=PlatformRegistry)
    module = UsernameModule(checker=mock_checker, registry=registry)
    module._owns_checker = True

    await module.close()
    mock_checker.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_skips_checker_when_not_owned() -> None:
    mock_checker = AsyncMock(spec=UsernameChecker)
    registry = MagicMock(spec=PlatformRegistry)
    module = UsernameModule(checker=mock_checker, registry=registry)
    module._owns_checker = False

    await module.close()
    mock_checker.close.assert_not_called()

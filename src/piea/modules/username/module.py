"""UsernameModule — BaseModule implementation for username enumeration.

Wraps UsernameChecker and translates PlatformCheckResult objects into
the standard ModuleFinding/ModuleResult format expected by the orchestrator.

Follows NFR-R1: any internal exception is caught and returned as a
ModuleResult with success=False. The module never raises.
"""

from __future__ import annotations

import logging

from piea.modules.base import (
    BaseModule,
    ModuleFinding,
    ModuleResult,
    ScanInputs,
    Severity,
)
from piea.modules.username.checker import (
    CheckStatus,
    PlatformCheckResult,
    UsernameChecker,
)
from piea.modules.username.platforms import PlatformRegistry, load_platform_registry
from piea.modules.username.rate_limiter import RateLimiterFactory

logger = logging.getLogger(__name__)

_MODULE_NAME = "username_enum"


class UsernameModule(BaseModule):
    """OSINT module that checks username presence across 50+ platforms.

    Uses async concurrent HTTP checks with per-platform rate limiting.
    Results are classified as found/not_found/error/rate_limited and
    only "found" results are reported as ModuleFinding objects.

    Args:
        checker: Optional pre-built UsernameChecker. If None, one is
            created lazily from the registry.
        registry: Optional pre-loaded PlatformRegistry. If None, the
            default registry is loaded from config/platforms.json.
    """

    def __init__(
        self,
        checker: UsernameChecker | None = None,
        registry: PlatformRegistry | None = None,
    ) -> None:
        self._registry = registry or load_platform_registry()
        self._rate_limiter_factory = RateLimiterFactory(cache=None)
        self._checker = checker or UsernameChecker(
            registry=self._registry,
            rate_limiter_factory=self._rate_limiter_factory,
        )
        self._owns_checker = checker is None

    @property
    def name(self) -> str:
        return _MODULE_NAME

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Run username existence checks across all registered platforms.

        Returns ModuleResult with success=False (not an exception) when:
        - No username is provided in inputs.
        - The checker raises an unhandled exception (NFR-R1).

        Args:
            inputs: Scan seed data. Only ``inputs.username`` is consumed.

        Returns:
            A ModuleResult with found platforms as findings.
        """
        if not inputs.username:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["No username provided for enumeration"],
            )

        try:
            results = await self._checker.check_all_platforms(inputs.username)
        except ValueError as exc:
            # Invalid username format — not a system error
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=[str(exc)],
            )
        except Exception as exc:  # noqa: BLE001
            # Broad catch satisfies NFR-R1: this module must never raise —
            # any unexpected checker failure must be returned as a failure result.
            logger.error("UsernameModule failed unexpectedly: %s", exc)
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=[f"Username enumeration failed: {exc}"],
            )

        findings, errors, metadata = _aggregate_results(results)
        return ModuleResult(
            module_name=self.name,
            success=True,
            findings=findings,
            errors=errors,
            metadata=metadata,
        )

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        if self._owns_checker:
            await self._checker.close()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _aggregate_results(
    results: list[PlatformCheckResult],
) -> tuple[list[ModuleFinding], list[str], dict[str, object]]:
    """Separate found/error/not-found results and build metadata.

    Args:
        results: Raw list of PlatformCheckResult from the checker.

    Returns:
        Tuple of (findings, errors, metadata) for inclusion in ModuleResult.
    """
    found = [r for r in results if r.status == CheckStatus.FOUND]
    errors = [
        f"{r.platform}: {r.error_message or r.status}"
        for r in results
        if r.status in (CheckStatus.ERROR, CheckStatus.RATE_LIMITED)
    ]
    categories: dict[str, int] = {}
    for r in found:
        categories[r.category] = categories.get(r.category, 0) + 1

    metadata: dict[str, object] = {
        "platforms_checked": len(results),
        "platforms_found": len(found),
        "platforms_not_found": sum(
            1 for r in results if r.status == CheckStatus.NOT_FOUND
        ),
        "platforms_error": sum(1 for r in results if r.status == CheckStatus.ERROR),
        "platforms_rate_limited": sum(
            1 for r in results if r.status == CheckStatus.RATE_LIMITED
        ),
        "categories_found": categories,
    }
    return [_result_to_finding(r) for r in found], errors, metadata


def _result_to_finding(result: PlatformCheckResult) -> ModuleFinding:
    """Convert a FOUND PlatformCheckResult to a ModuleFinding.

    Args:
        result: A PlatformCheckResult with status FOUND.

    Returns:
        A ModuleFinding for inclusion in the scan report.
    """
    return ModuleFinding(
        finding_type="username_found",
        severity=Severity.MEDIUM,
        category="username",
        title=f"Username found on {result.platform}",
        description=(
            f"The username was found on {result.platform} ({result.category} platform). "
            f"Profile URL: {result.url}"
        ),
        platform=result.platform,
        evidence={
            "platform": result.platform,
            "url": result.url,
            "category": result.category,
            "checked_at": result.checked_at,
        },
        remediation_action=(
            "Review your public profile on this platform to ensure no sensitive "
            "personal information is exposed. Consider restricting visibility if possible."
        ),
        remediation_effort="easy",
        weight=0.4,
    )

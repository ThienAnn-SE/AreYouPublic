"""Platform registry for username enumeration.

Loads platform definitions from config/platforms.json and provides
a typed interface for querying them. New platforms are added exclusively
via the JSON file — no Python code changes required (NFR-SC2).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default path: <repo_root>/config/platforms.json
_DEFAULT_CONFIG_PATH = (
    Path(__file__).parent.parent.parent.parent.parent / "config" / "platforms.json"
)

_REQUIRED_FIELDS = frozenset(
    {
        "platform",
        "url_pattern",
        "expected_status_found",
        "expected_status_not_found",
        "category",
        "has_public_api",
        "rate_limit_requests_per_minute",
    }
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class CheckMethod(StrEnum):
    """HTTP method used to check for username existence."""

    GET = "GET"
    HEAD = "HEAD"


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Configuration for a single platform username check.

    Attributes:
        platform: Human-readable platform name.
        url_pattern: URL template with ``{username}`` placeholder.
        expected_status_found: HTTP status indicating the username exists.
        expected_status_not_found: HTTP status indicating it does not exist.
        category: Broad category (e.g. "social_media", "development").
        has_public_api: Whether an official public API is available.
        rate_limit_requests_per_minute: Recommended per-platform RPM cap.
        check_method: HTTP method to use for the existence check.
    """

    platform: str
    url_pattern: str
    expected_status_found: int
    expected_status_not_found: int
    category: str
    has_public_api: bool
    rate_limit_requests_per_minute: int
    check_method: CheckMethod = CheckMethod.GET

    def build_url(self, username: str) -> str:
        """Substitute *username* into the URL pattern.

        Args:
            username: Already-validated username string.

        Returns:
            The fully resolved profile URL.
        """
        return self.url_pattern.format(username=username)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class PlatformRegistry:
    """Loads and queries platform definitions from a JSON config file.

    The registry is loaded once at construction time. All query methods are
    synchronous because the data lives in memory after the initial load.

    Args:
        config_path: Path to ``platforms.json``. Defaults to
            ``<repo_root>/config/platforms.json``.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        self._platforms: list[PlatformConfig] = []
        self._loaded = False

    def load(self) -> None:
        """Load and validate platform definitions from the JSON file.

        Raises:
            FileNotFoundError: If the config file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            ValueError: If any platform entry is missing required fields.
        """
        raw_text = self._config_path.read_text(encoding="utf-8")
        raw_list: list[dict[str, Any]] = json.loads(raw_text)

        platforms = []
        for i, raw in enumerate(raw_list):
            platforms.append(_parse_platform(raw, index=i))

        self._platforms = platforms
        self._loaded = True
        logger.info("Loaded %d platforms from %s", len(platforms), self._config_path)

    def get_all(self) -> list[PlatformConfig]:
        """Return all loaded platform configurations."""
        self._ensure_loaded()
        return list(self._platforms)

    def get_by_category(self, category: str) -> list[PlatformConfig]:
        """Return platforms matching the given category.

        Args:
            category: Category string to filter by (exact match).

        Returns:
            Filtered list of PlatformConfig objects.
        """
        self._ensure_loaded()
        return [p for p in self._platforms if p.category == category]

    def count(self) -> int:
        """Return the number of loaded platforms."""
        self._ensure_loaded()
        return len(self._platforms)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()


# ---------------------------------------------------------------------------
# Module-level factory
# ---------------------------------------------------------------------------


def load_platform_registry(config_path: Path | None = None) -> PlatformRegistry:
    """Create and load a PlatformRegistry.

    Args:
        config_path: Override the default config path (useful in tests).

    Returns:
        A fully loaded PlatformRegistry.
    """
    registry = PlatformRegistry(config_path=config_path)
    registry.load()
    return registry


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_check_method(platform_name: str, raw_value: str) -> CheckMethod:
    """Parse and validate the check_method field.

    Args:
        platform_name: Used in error messages only.
        raw_value: The raw string value from JSON.

    Returns:
        A CheckMethod enum member.

    Raises:
        ValueError: If the value is not a supported HTTP method.
    """
    normalized = raw_value.upper()
    try:
        return CheckMethod(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Platform '{platform_name}' has invalid check_method: {normalized!r}. "
            f"Must be one of: {[m.value for m in CheckMethod]}"
        ) from exc


def _parse_platform(raw: dict[str, Any], index: int) -> PlatformConfig:
    """Parse and validate a single raw platform dict.

    Args:
        raw: Parsed JSON object for one platform.
        index: Position in the array (used in error messages only).

    Returns:
        A validated PlatformConfig.

    Raises:
        ValueError: If required fields are missing or values are invalid.
    """
    missing = _REQUIRED_FIELDS - raw.keys()
    if missing:
        raise ValueError(
            f"Platform entry at index {index} is missing required fields: {sorted(missing)}"
        )

    url_pattern = str(raw["url_pattern"])
    if "{username}" not in url_pattern:
        raise ValueError(
            f"Platform '{raw['platform']}' url_pattern must contain {{username}} placeholder"
        )

    check_method = _parse_check_method(
        str(raw["platform"]), str(raw.get("check_method", "GET"))
    )

    return PlatformConfig(
        platform=str(raw["platform"]),
        url_pattern=url_pattern,
        expected_status_found=int(raw["expected_status_found"]),
        expected_status_not_found=int(raw["expected_status_not_found"]),
        category=str(raw["category"]),
        has_public_api=bool(raw["has_public_api"]),
        rate_limit_requests_per_minute=int(raw["rate_limit_requests_per_minute"]),
        check_method=check_method,
    )

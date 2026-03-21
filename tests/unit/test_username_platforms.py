"""Tests for the platform registry (T2.1).

Verifies that PlatformRegistry correctly loads, validates, and queries
the platforms.json config file. All tests use either the real config or
an in-memory JSON string — no network calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from piea.modules.username.platforms import (
    CheckMethod,
    PlatformConfig,
    PlatformRegistry,
    load_platform_registry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_json(tmp_path: Path, data: object) -> Path:
    """Write *data* as JSON to a temp file and return its path."""
    p = tmp_path / "platforms.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _minimal_platform(overrides: dict | None = None) -> dict:
    """Return a minimal valid platform dict."""
    base: dict = {
        "platform": "TestSite",
        "url_pattern": "https://example.com/{username}",
        "expected_status_found": 200,
        "expected_status_not_found": 404,
        "category": "test",
        "has_public_api": False,
        "rate_limit_requests_per_minute": 30,
    }
    if overrides:
        base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_real_config_returns_50_plus_platforms() -> None:
    """The production config/platforms.json must have at least 50 entries."""
    registry = load_platform_registry()
    assert registry.count() >= 50


def test_get_all_returns_list_of_platform_configs() -> None:
    registry = load_platform_registry()
    platforms = registry.get_all()
    assert all(isinstance(p, PlatformConfig) for p in platforms)


def test_get_by_category_filters_correctly(tmp_path: Path) -> None:
    data = [
        _minimal_platform({"platform": "DevSite", "category": "development"}),
        _minimal_platform({"platform": "SocialSite", "category": "social_media"}),
        _minimal_platform({"platform": "DevSite2", "category": "development"}),
    ]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    dev = registry.get_by_category("development")
    assert len(dev) == 2
    assert all(p.category == "development" for p in dev)


def test_get_by_category_empty_when_no_match(tmp_path: Path) -> None:
    data = [_minimal_platform({"category": "development"})]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    assert registry.get_by_category("gaming") == []


def test_count_matches_number_of_entries(tmp_path: Path) -> None:
    data = [_minimal_platform() for _ in range(7)]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    assert registry.count() == 7


def test_check_method_defaults_to_get(tmp_path: Path) -> None:
    data = [_minimal_platform()]  # no check_method field
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    platform = registry.get_all()[0]
    assert platform.check_method == CheckMethod.GET


def test_head_check_method_is_parsed(tmp_path: Path) -> None:
    data = [_minimal_platform({"check_method": "HEAD"})]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    platform = registry.get_all()[0]
    assert platform.check_method == CheckMethod.HEAD


def test_build_url_substitutes_username(tmp_path: Path) -> None:
    data = [
        _minimal_platform({"url_pattern": "https://example.com/{username}/profile"})
    ]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    platform = registry.get_all()[0]
    assert platform.build_url("alice") == "https://example.com/alice/profile"


def test_lazy_load_on_first_query(tmp_path: Path) -> None:
    """Registry should load on first access, not at construction time."""
    registry = PlatformRegistry(
        config_path=_write_json(tmp_path, [_minimal_platform()])
    )
    assert not registry._loaded  # not yet loaded
    registry.get_all()
    assert registry._loaded


def test_load_platform_registry_factory(tmp_path: Path) -> None:
    data = [_minimal_platform(), _minimal_platform({"platform": "Other"})]
    path = _write_json(tmp_path, data)
    registry = load_platform_registry(config_path=path)
    assert registry.count() == 2


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_missing_required_field_raises_value_error(tmp_path: Path) -> None:
    data = [{"platform": "Bad", "url_pattern": "https://example.com/{username}"}]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    with pytest.raises(ValueError, match="missing required fields"):
        registry.load()


def test_url_pattern_without_placeholder_raises(tmp_path: Path) -> None:
    data = [_minimal_platform({"url_pattern": "https://example.com/profile"})]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    with pytest.raises(ValueError, match=r"\{username\}"):
        registry.load()


def test_invalid_check_method_raises(tmp_path: Path) -> None:
    data = [_minimal_platform({"check_method": "POST"})]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    with pytest.raises(ValueError, match="invalid check_method"):
        registry.load()


def test_malformed_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "platforms.json"
    p.write_text("{not valid json", encoding="utf-8")
    registry = PlatformRegistry(config_path=p)
    import json as _json

    with pytest.raises(_json.JSONDecodeError):
        registry.load()


def test_file_not_found_raises(tmp_path: Path) -> None:
    registry = PlatformRegistry(config_path=tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        registry.load()


def test_get_all_returns_independent_copy(tmp_path: Path) -> None:
    """Mutations to the returned list must not affect the registry's internal list."""
    data = [_minimal_platform()]
    registry = PlatformRegistry(config_path=_write_json(tmp_path, data))
    first = registry.get_all()
    first.clear()
    assert registry.count() == 1

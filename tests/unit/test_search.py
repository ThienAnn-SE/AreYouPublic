"""Unit tests for SearchModule (T3.1).

Tests cover:
  - SearchHit and SearchQueryResult construction
  - Query construction (dynamic priority, edge cases)
  - SearchClient HTTP parsing and error mapping
  - SearchModule.execute() finding generation, deduplication, error handling
  - Data broker detection (www prefix, subdomains)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from piea.modules.base import (
    ScanInputs,
)
from piea.modules.search import (
    SearchHit,
    SearchModule,
    SearchQueryResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BROKERS_CONFIG_PATH = Path("config/data_brokers.json")
CSE_BASE = "https://www.googleapis.com/customsearch/v1"

SAMPLE_CSE_RESPONSE = {
    "items": [
        {
            "title": "Jane Doe - LinkedIn",
            "snippet": "Jane Doe | Software Engineer at Acme Corp.",
            "link": "https://www.linkedin.com/in/janedoe",
            "displayLink": "www.linkedin.com",
        },
        {
            "title": "Jane Doe profile | Spokeo",
            "snippet": "Find Jane Doe's contact info.",
            "link": "https://www.spokeo.com/Jane-Doe",
            "displayLink": "www.spokeo.com",
        },
    ]
}


@pytest.fixture
def scan_inputs_full() -> ScanInputs:
    return ScanInputs(
        email="jane@example.com", username="janedoe", full_name="Jane Doe"
    )


@pytest.fixture
def scan_inputs_name_only() -> ScanInputs:
    return ScanInputs(full_name="Jane Doe")


@pytest.fixture
def search_module() -> SearchModule:
    return SearchModule(
        api_key="test-key",
        engine_id="test-engine",
        brokers_config_path=BROKERS_CONFIG_PATH,
    )


# ---------------------------------------------------------------------------
# Task 2: Data model tests
# ---------------------------------------------------------------------------


def test_search_hit_construction() -> None:
    hit = SearchHit(
        title="Jane Doe - LinkedIn",
        snippet="Software Engineer",
        url="https://linkedin.com/in/janedoe",
        display_link="linkedin.com",
    )
    assert hit.title == "Jane Doe - LinkedIn"
    assert hit.url == "https://linkedin.com/in/janedoe"


def test_search_query_result_hits_are_immutable() -> None:
    hit = SearchHit(title="t", snippet="s", url="https://x.com", display_link="x.com")
    result = SearchQueryResult(query="test", hits=(hit,))
    with pytest.raises(AttributeError):
        result.hits = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Task 3: Query construction
# ---------------------------------------------------------------------------


def test_query_construction_all_inputs(search_module: SearchModule) -> None:
    """All four inputs available: builds 3 queries in priority order."""
    inputs = ScanInputs(
        email="jane@example.com", username="janedoe", full_name="Jane Doe"
    )
    queries = search_module._build_queries(inputs)
    assert queries == ['"Jane Doe"', '"Jane Doe" "@example.com"', '"janedoe"']
    assert len(queries) == 3


def test_query_construction_partial_inputs(search_module: SearchModule) -> None:
    """No email: skips priority 2, fills from username and name+username."""
    inputs = ScanInputs(username="janedoe", full_name="Jane Doe")
    queries = search_module._build_queries(inputs)
    assert '"Jane Doe"' in queries
    assert '"janedoe"' in queries
    assert len(queries) <= 3


def test_query_construction_no_inputs(search_module: SearchModule) -> None:
    """All inputs None: returns empty list."""
    queries = search_module._build_queries(ScanInputs())
    assert queries == []


def test_query_construction_deduplication(search_module: SearchModule) -> None:
    """username == full_name: duplicate query is removed."""
    inputs = ScanInputs(full_name="janedoe", username="janedoe")
    queries = search_module._build_queries(inputs)
    assert queries.count('"janedoe"') == 1

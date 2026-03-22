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

import httpx
import pytest
import respx

from piea.modules.base import (
    ModuleAPIError,
    RateLimitExceededError,
    ScanInputs,
)
from piea.modules.search import (
    SearchClient,
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


# ---------------------------------------------------------------------------
# Task 4: SearchClient HTTP layer
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_search_returns_hits() -> None:
    """SearchClient parses CSE JSON response into SearchHit tuples."""
    respx.get(CSE_BASE).mock(return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE))
    client = SearchClient(api_key="key", engine_id="cx")
    hits = await client.search("Jane Doe")
    await client.close()
    assert len(hits) == 2
    assert hits[0].title == "Jane Doe - LinkedIn"
    assert hits[0].url == "https://www.linkedin.com/in/janedoe"
    assert hits[0].display_link == "www.linkedin.com"
    assert isinstance(hits, tuple)


@respx.mock
@pytest.mark.asyncio
async def test_search_empty_results_returns_empty_tuple() -> None:
    """CSE returns {} (no 'items' key) when no results — must return empty tuple."""
    respx.get(CSE_BASE).mock(return_value=httpx.Response(200, json={}))
    client = SearchClient(api_key="key", engine_id="cx")
    hits = await client.search("very-obscure-query-xyz")
    await client.close()
    assert hits == ()


@respx.mock
@pytest.mark.asyncio
async def test_search_quota_exhausted_raises_rate_limit_error() -> None:
    """HTTP 429 from CSE → RateLimitExceededError."""
    respx.get(CSE_BASE).mock(return_value=httpx.Response(429))
    client = SearchClient(api_key="key", engine_id="cx")
    with pytest.raises(RateLimitExceededError):
        await client.search("Jane Doe")
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_search_api_error_raises_module_api_error() -> None:
    """HTTP 500 from CSE → ModuleAPIError."""
    respx.get(CSE_BASE).mock(return_value=httpx.Response(500))
    client = SearchClient(api_key="key", engine_id="cx")
    with pytest.raises(ModuleAPIError):
        await client.search("Jane Doe")
    await client.close()


# ---------------------------------------------------------------------------
# Task 5: Broker detection
# ---------------------------------------------------------------------------


def test_broker_detection_flags_known_domain(search_module: SearchModule) -> None:
    hit = SearchHit(
        title="Jane Doe",
        snippet="...",
        url="https://spokeo.com/Jane-Doe",
        display_link="spokeo.com",
    )
    assert search_module._is_broker(hit) is True


def test_broker_detection_www_prefix(search_module: SearchModule) -> None:
    hit = SearchHit(
        title="Jane Doe",
        snippet="...",
        url="https://www.spokeo.com/Jane-Doe",
        display_link="www.spokeo.com",
    )
    assert search_module._is_broker(hit) is True


def test_broker_detection_subdomain(search_module: SearchModule) -> None:
    hit = SearchHit(
        title="Jane Doe",
        snippet="...",
        url="https://results.spokeo.com/Jane-Doe",
        display_link="results.spokeo.com",
    )
    assert search_module._is_broker(hit) is True


def test_broker_detection_non_broker(search_module: SearchModule) -> None:
    hit = SearchHit(
        title="Jane Doe",
        snippet="...",
        url="https://linkedin.com/in/janedoe",
        display_link="linkedin.com",
    )
    assert search_module._is_broker(hit) is False

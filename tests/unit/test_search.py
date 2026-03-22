"""Unit tests for the Search module (T3.1 / T3.3).

Tests cover:
  - Query construction (_build_queries, Option A strategy)
  - Result categorization (all 6 types)
  - DataBrokerDetector (domain lookup, opt-out URL retrieval)
  - SearchClient: success path, empty results, 429 retry, 403 quota, 5xx error
  - SearchModule.execute(): full success, quota failure, missing config,
    no inputs, entity disambiguation (name-only → INFO severity)
  - EntityResolver: common-name detection, signal extraction, result matching,
    filter_results logic (T3.3)
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from piea.modules.base import ScanInputs, Severity
from piea.modules.search import (
    COMMON_NAMES,
    GOOGLE_CSE_BASE,
    DataBrokerDetector,
    DisambiguationResult,
    EntityResolver,
    ResultCategorizer,
    SearchAPIError,
    SearchClient,
    SearchModule,
    SearchQuotaError,
    SearchResult,
    _extract_domain,
    _sanitize,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_CSE_RESPONSE = {
    "kind": "customsearch#search",
    "items": [
        {
            "title": "Alice Example - LinkedIn",
            "snippet": "Alice Example | Software Engineer at Acme Corp.",
            "link": "https://www.linkedin.com/in/alice-example",
            "displayLink": "www.linkedin.com",
        },
        {
            "title": "Alice Example on Spokeo",
            "snippet": "Alice Example, age 32. Lives in San Francisco, CA.",
            "link": "https://www.spokeo.com/Alice-Example",
            "displayLink": "www.spokeo.com",
        },
        {
            "title": "Alice Example | Hacker News",
            "snippet": "Submissions and comments by Alice Example on Hacker News.",
            "link": "https://news.ycombinator.com/user?id=alice-example",
            "displayLink": "news.ycombinator.com",
        },
        {
            "title": "Alice Example - Reuters",
            "snippet": "Alice Example comments on open-source licensing.",
            "link": "https://www.reuters.com/article/alice-example",
            "displayLink": "www.reuters.com",
        },
        {
            "title": "Alice Example - ResearchGate",
            "snippet": "Profile of Alice Example, researcher.",
            "link": "https://www.researchgate.net/profile/Alice-Example",
            "displayLink": "www.researchgate.net",
        },
        {
            "title": "Alice Example personal site",
            "snippet": "Welcome to Alice's blog.",
            "link": "https://alice-example.com/about",
            "displayLink": "alice-example.com",
        },
    ],
}

EMPTY_CSE_RESPONSE: dict[str, Any] = {"kind": "customsearch#search"}


# ---------------------------------------------------------------------------
# _extract_domain
# ---------------------------------------------------------------------------


class TestExtractDomain:
    def test_strips_www_prefix(self):
        assert _extract_domain("https://www.linkedin.com/in/alice") == "linkedin.com"

    def test_preserves_non_www_subdomain(self):
        assert (
            _extract_domain("https://news.ycombinator.com/user?id=x")
            == "news.ycombinator.com"
        )

    def test_plain_domain(self):
        assert _extract_domain("https://spokeo.com/Alice") == "spokeo.com"

    def test_empty_string_on_invalid_url(self):
        assert _extract_domain("not-a-url") == ""

    def test_empty_string_on_blank(self):
        assert _extract_domain("") == ""


# ---------------------------------------------------------------------------
# _sanitize
# ---------------------------------------------------------------------------


class TestSanitize:
    def test_strips_parentheses(self):
        assert _sanitize("Alice (Example)") == "Alice Example"

    def test_strips_angle_brackets(self):
        assert _sanitize("Alice <Example>") == "Alice Example"

    def test_strips_backslash(self):
        assert _sanitize("Alice\\Example") == "AliceExample"

    def test_returns_empty_for_none(self):
        assert _sanitize(None) == ""

    def test_returns_empty_for_blank(self):
        assert _sanitize("   ") == ""

    def test_strips_surrounding_whitespace(self):
        assert _sanitize("  Alice Example  ") == "Alice Example"

    def test_normal_name_unchanged(self):
        assert _sanitize("Alice Example") == "Alice Example"


# ---------------------------------------------------------------------------
# DataBrokerDetector
# ---------------------------------------------------------------------------


class TestDataBrokerDetector:
    def setup_method(self):
        self.detector = DataBrokerDetector()

    def test_spokeo_is_data_broker(self):
        assert self.detector.is_data_broker("https://www.spokeo.com/Alice-Example")

    def test_whitepages_is_data_broker(self):
        assert self.detector.is_data_broker(
            "https://www.whitepages.com/name/Alice-Example"
        )

    def test_linkedin_is_not_data_broker(self):
        assert not self.detector.is_data_broker("https://www.linkedin.com/in/alice")

    def test_subdomain_of_broker_detected(self):
        assert self.detector.is_data_broker("https://people.spokeo.com/Alice")

    def test_minimum_20_broker_domains(self):
        assert len(self.detector.DATA_BROKER_DOMAINS) >= 20

    def test_opt_out_url_returned_for_spokeo(self):
        url = self.detector.get_opt_out_url("https://www.spokeo.com/Alice")
        assert url is not None
        assert "spokeo" in url

    def test_opt_out_url_none_for_unknown_broker(self):
        # A broker in DATA_BROKER_DOMAINS but not in DATA_BROKER_OPT_OUT
        url = self.detector.get_opt_out_url("https://www.anywho.com/Alice")
        assert url is None

    def test_opt_out_url_none_for_non_broker(self):
        assert (
            self.detector.get_opt_out_url("https://www.linkedin.com/in/alice") is None
        )


# ---------------------------------------------------------------------------
# ResultCategorizer
# ---------------------------------------------------------------------------


class TestResultCategorizer:
    def setup_method(self):
        self.categorizer = ResultCategorizer(DataBrokerDetector())

    def test_linkedin_is_social_profile(self):
        assert (
            self.categorizer.classify("https://www.linkedin.com/in/alice")
            == "social_profile"
        )

    def test_twitter_is_social_profile(self):
        assert (
            self.categorizer.classify("https://twitter.com/alice") == "social_profile"
        )

    def test_hn_is_forum_post(self):
        assert (
            self.categorizer.classify("https://news.ycombinator.com/user?id=alice")
            == "forum_post"
        )

    def test_stackoverflow_is_forum_post(self):
        assert (
            self.categorizer.classify("https://stackoverflow.com/users/1/alice")
            == "forum_post"
        )

    def test_researchgate_is_professional_directory(self):
        assert (
            self.categorizer.classify("https://www.researchgate.net/profile/Alice")
            == "professional_directory"
        )

    def test_reuters_is_news_mention(self):
        assert (
            self.categorizer.classify("https://www.reuters.com/article/alice")
            == "news_mention"
        )

    def test_spokeo_is_data_broker(self):
        assert (
            self.categorizer.classify("https://www.spokeo.com/Alice") == "data_broker"
        )

    def test_unknown_domain_is_uncategorized(self):
        assert (
            self.categorizer.classify("https://alice-example.com/about")
            == "uncategorized"
        )

    def test_data_broker_takes_priority_over_social(self):
        # If somehow a broker domain matched social patterns too, data_broker wins
        assert (
            self.categorizer.classify("https://www.spokeo.com/Alice") == "data_broker"
        )


# ---------------------------------------------------------------------------
# SearchClient — HTTP layer (respx mocks)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestSearchClient:
    def _make_client(self, http_client: httpx.AsyncClient) -> SearchClient:
        return SearchClient(
            api_key="test-api-key",
            engine_id="test-engine-id",
            http_client=http_client,
        )

    @respx.mock
    async def test_search_returns_parsed_results(self):
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE)
        )
        async with httpx.AsyncClient() as http:
            client = self._make_client(http)
            results = await client.search('"Alice Example"')

        assert len(results) == 6
        linkedin = next(r for r in results if "linkedin" in r.url)
        assert linkedin.category == "social_profile"

    @respx.mock
    async def test_search_returns_empty_list_when_no_items(self):
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=EMPTY_CSE_RESPONSE)
        )
        async with httpx.AsyncClient() as http:
            client = self._make_client(http)
            results = await client.search('"Alice Example"')

        assert results == []

    @respx.mock
    async def test_search_raises_quota_error_on_403(self):
        respx.get(GOOGLE_CSE_BASE).mock(return_value=httpx.Response(403))
        async with httpx.AsyncClient() as http:
            client = self._make_client(http)
            with pytest.raises(SearchQuotaError):
                await client.search('"Alice Example"')

    @respx.mock
    async def test_search_raises_quota_error_after_three_429s(self):
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "0"})
        )
        async with httpx.AsyncClient() as http:
            client = self._make_client(http)
            with pytest.raises(SearchQuotaError):
                await client.search('"Alice Example"')

    @respx.mock
    async def test_search_raises_api_error_on_500(self):
        respx.get(GOOGLE_CSE_BASE).mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as http:
            client = self._make_client(http)
            with pytest.raises(SearchAPIError) as exc_info:
                await client.search('"Alice Example"')
        assert exc_info.value.status_code == 500

    @respx.mock
    async def test_spokeo_result_flagged_as_data_broker(self):
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE)
        )
        async with httpx.AsyncClient() as http:
            client = self._make_client(http)
            results = await client.search('"Alice Example"')

        spokeo = next(r for r in results if "spokeo" in r.url)
        assert spokeo.is_data_broker is True
        assert spokeo.opt_out_url is not None
        assert "spokeo" in spokeo.opt_out_url

    @respx.mock
    async def test_linkedin_result_not_flagged_as_data_broker(self):
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE)
        )
        async with httpx.AsyncClient() as http:
            client = self._make_client(http)
            results = await client.search('"Alice Example"')

        linkedin = next(r for r in results if "linkedin" in r.url)
        assert linkedin.is_data_broker is False
        assert linkedin.opt_out_url is None


# ---------------------------------------------------------------------------
# SearchModule._build_queries (Option A)
# ---------------------------------------------------------------------------


class TestBuildQueries:
    def setup_method(self):
        self.module = SearchModule(
            client=SearchClient(
                api_key="k", engine_id="e", http_client=httpx.AsyncClient()
            )
        )

    def test_name_only_produces_two_queries(self):
        queries = self.module._build_queries(ScanInputs(full_name="Alice Example"))
        assert len(queries) == 2
        assert queries[0] == '"Alice Example"'
        assert "site:linkedin.com" in queries[1]

    def test_name_email_username_produces_three_queries(self):
        queries = self.module._build_queries(
            ScanInputs(
                full_name="Alice Example", email="alice@example.com", username="alice"
            )
        )
        assert len(queries) == 3
        assert queries[0] == '"Alice Example"'
        assert "site:linkedin.com" in queries[1]
        assert '"alice@example.com"' in queries[2]
        assert '"alice"' in queries[2]

    def test_email_only_produces_one_query(self):
        queries = self.module._build_queries(ScanInputs(email="alice@example.com"))
        assert len(queries) == 1
        assert queries[0] == '"alice@example.com"'

    def test_no_inputs_returns_empty_list(self):
        queries = self.module._build_queries(ScanInputs())
        assert queries == []

    def test_sanitizes_name_with_parens(self):
        queries = self.module._build_queries(ScanInputs(full_name="Alice (Example)"))
        assert "()" not in queries[0]

    def test_max_three_queries_even_with_all_inputs(self):
        queries = self.module._build_queries(
            ScanInputs(
                full_name="Alice", email="alice@example.com", username="alice123"
            )
        )
        assert len(queries) <= 3


# ---------------------------------------------------------------------------
# SearchModule.execute() end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestSearchModuleExecute:
    @respx.mock
    async def test_execute_returns_success_with_findings(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "test-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "test-cx"
        )
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE)
        )
        module = SearchModule(
            client=SearchClient(
                api_key="test-key",
                engine_id="test-cx",
                http_client=httpx.AsyncClient(),
            )
        )
        result = await module.execute(
            ScanInputs(full_name="Alice Example", email="alice@example.com")
        )
        assert result.success is True
        assert len(result.findings) > 0

    @respx.mock
    async def test_spokeo_hit_produces_high_severity_finding(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "test-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "test-cx"
        )
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE)
        )
        module = SearchModule(
            client=SearchClient(
                api_key="test-key",
                engine_id="test-cx",
                http_client=httpx.AsyncClient(),
            )
        )
        result = await module.execute(
            ScanInputs(full_name="Alice Example", email="alice@example.com")
        )
        broker_findings = [
            f for f in result.findings if f.finding_type == "data_broker_listing"
        ]
        assert len(broker_findings) >= 1
        assert all(f.severity == Severity.HIGH for f in broker_findings)
        spokeo_finding = next(f for f in broker_findings if "spokeo" in f.platform)
        assert spokeo_finding.remediation_url is not None

    @respx.mock
    async def test_name_only_summary_finding_is_info_severity(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "test-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "test-cx"
        )
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE)
        )
        module = SearchModule(
            client=SearchClient(
                api_key="test-key",
                engine_id="test-cx",
                http_client=httpx.AsyncClient(),
            )
        )
        result = await module.execute(ScanInputs(full_name="Alice Example"))
        summary = next(f for f in result.findings if f.finding_type == "web_presence")
        assert summary.severity == Severity.INFO

    @respx.mock
    async def test_name_and_email_summary_finding_is_medium_severity(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "test-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "test-cx"
        )
        respx.get(GOOGLE_CSE_BASE).mock(
            return_value=httpx.Response(200, json=SAMPLE_CSE_RESPONSE)
        )
        module = SearchModule(
            client=SearchClient(
                api_key="test-key",
                engine_id="test-cx",
                http_client=httpx.AsyncClient(),
            )
        )
        result = await module.execute(
            ScanInputs(full_name="Alice Example", email="alice@example.com")
        )
        summary = next(f for f in result.findings if f.finding_type == "web_presence")
        assert summary.severity == Severity.MEDIUM

    async def test_missing_api_key_returns_failure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.search.settings.google_cse_api_key", "")
        monkeypatch.setattr("piea.modules.search.settings.google_cse_engine_id", "")
        module = SearchModule()
        result = await module.execute(ScanInputs(full_name="Alice Example"))
        assert result.success is False
        assert result.errors

    async def test_no_inputs_returns_failure(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "test-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "test-cx"
        )
        module = SearchModule(
            client=SearchClient(
                api_key="test-key",
                engine_id="test-cx",
                http_client=httpx.AsyncClient(),
            )
        )
        result = await module.execute(ScanInputs())
        assert result.success is False
        assert result.errors

    @respx.mock
    async def test_quota_error_recorded_in_errors(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "test-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "test-cx"
        )
        respx.get(GOOGLE_CSE_BASE).mock(return_value=httpx.Response(403))
        module = SearchModule(
            client=SearchClient(
                api_key="test-key",
                engine_id="test-cx",
                http_client=httpx.AsyncClient(),
            )
        )
        result = await module.execute(ScanInputs(full_name="Alice Example"))
        assert result.errors
        assert any("quota" in e.lower() for e in result.errors)

    @respx.mock
    async def test_module_name_is_search(self):
        module = SearchModule(
            client=SearchClient(
                api_key="k", engine_id="e", http_client=httpx.AsyncClient()
            )
        )
        assert module.name == "search"


# ---------------------------------------------------------------------------
# EntityResolver (T3.3)
# ---------------------------------------------------------------------------


def _make_result(
    title: str = "",
    snippet: str = "",
    url: str = "https://example.com",
    category: str = "uncategorized",
    is_data_broker: bool = False,
    opt_out_url: str | None = None,
) -> SearchResult:
    """Build a minimal SearchResult for testing."""
    return SearchResult(
        title=title,
        snippet=snippet,
        url=url,
        display_link="example.com",
        category=category,
        is_data_broker=is_data_broker,
        opt_out_url=opt_out_url,
    )


class TestEntityResolverIsCommonName:
    """Tests for EntityResolver.is_common_name()."""

    def test_common_first_name_returns_true(self):
        resolver = EntityResolver()
        assert resolver.is_common_name("John Smith") is True

    def test_common_first_name_case_insensitive(self):
        resolver = EntityResolver()
        assert resolver.is_common_name("MARY Johnson") is True

    def test_uncommon_name_returns_false(self):
        resolver = EntityResolver()
        assert resolver.is_common_name("Xiomara Quetzalcoatl") is False

    def test_none_returns_false(self):
        resolver = EntityResolver()
        assert resolver.is_common_name(None) is False

    def test_empty_string_returns_false(self):
        resolver = EntityResolver()
        assert resolver.is_common_name("") is False

    def test_whitespace_only_returns_false(self):
        resolver = EntityResolver()
        assert resolver.is_common_name("   ") is False

    def test_single_common_name_token_returns_true(self):
        resolver = EntityResolver()
        assert resolver.is_common_name("james") is True

    def test_custom_common_names_set_used(self):
        resolver = EntityResolver(common_names=frozenset({"zeus"}))
        assert resolver.is_common_name("Zeus Thunderbolt") is True
        assert resolver.is_common_name("John Smith") is False

    def test_common_names_constant_non_empty(self):
        assert len(COMMON_NAMES) > 0

    def test_all_names_in_constant_are_lowercase(self):
        assert all(n == n.lower() for n in COMMON_NAMES)


class TestEntityResolverExtractSignals:
    """Tests for EntityResolver.extract_signals()."""

    def test_email_and_username_extracted(self):
        resolver = EntityResolver()
        signals = resolver.extract_signals(
            ScanInputs(email="alice@example.com", username="alice99")
        )
        assert "alice@example.com" in signals
        assert "alice99" in signals

    def test_full_name_excluded(self):
        resolver = EntityResolver()
        signals = resolver.extract_signals(ScanInputs(full_name="John Smith"))
        assert signals == []

    def test_signals_are_lowercased(self):
        resolver = EntityResolver()
        signals = resolver.extract_signals(ScanInputs(email="ALICE@Example.COM"))
        assert "alice@example.com" in signals

    def test_extra_signals_included(self):
        resolver = EntityResolver()
        signals = resolver.extract_signals(
            ScanInputs(email="a@b.com"),
            extra_signals=["Acme Corp", "New York"],
        )
        assert "acme corp" in signals
        assert "new york" in signals

    def test_none_inputs_yield_empty_list(self):
        resolver = EntityResolver()
        assert resolver.extract_signals(ScanInputs()) == []

    def test_duplicate_signals_deduplicated(self):
        resolver = EntityResolver()
        signals = resolver.extract_signals(
            ScanInputs(email="a@b.com"),
            extra_signals=["a@b.com"],
        )
        assert signals.count("a@b.com") == 1

    def test_blank_extra_signals_ignored(self):
        resolver = EntityResolver()
        signals = resolver.extract_signals(ScanInputs(), extra_signals=["", "  "])
        assert signals == []


class TestEntityResolverResultMatchesSignal:
    """Tests for EntityResolver.result_matches_signal()."""

    def test_email_in_snippet_matches(self):
        resolver = EntityResolver()
        result = _make_result(snippet="Contact: alice@example.com for more info.")
        assert resolver.result_matches_signal(result, ["alice@example.com"]) is True

    def test_username_in_title_matches(self):
        resolver = EntityResolver()
        result = _make_result(title="Profile page of alice99")
        assert resolver.result_matches_signal(result, ["alice99"]) is True

    def test_signal_in_url_matches(self):
        resolver = EntityResolver()
        result = _make_result(url="https://example.com/user/alice99")
        assert resolver.result_matches_signal(result, ["alice99"]) is True

    def test_no_signal_match_returns_false(self):
        resolver = EntityResolver()
        result = _make_result(title="Generic page", snippet="Nothing relevant here.")
        assert (
            resolver.result_matches_signal(result, ["alice99", "alice@example.com"])
            is False
        )

    def test_empty_signals_returns_false(self):
        resolver = EntityResolver()
        result = _make_result(snippet="alice99 is here")
        assert resolver.result_matches_signal(result, []) is False

    def test_matching_is_case_insensitive(self):
        resolver = EntityResolver()
        result = _make_result(snippet="Works at ACME CORP in Finance.")
        assert resolver.result_matches_signal(result, ["acme corp"]) is True

    def test_any_one_signal_sufficient(self):
        resolver = EntityResolver()
        result = _make_result(snippet="Profile of alice99.")
        # Only the second signal matches
        assert resolver.result_matches_signal(result, ["nomatch", "alice99"]) is True


class TestEntityResolverFilterResults:
    """Tests for EntityResolver.filter_results()."""

    def _results_with_and_without_signal(self) -> list[SearchResult]:
        return [
            _make_result(snippet="alice@example.com is here", url="https://a.com"),
            _make_result(snippet="no signal at all", url="https://b.com"),
            _make_result(title="alice@example.com profile", url="https://c.com"),
        ]

    def test_non_common_name_passes_all_through(self):
        resolver = EntityResolver()
        results = self._results_with_and_without_signal()
        disambiguation = resolver.filter_results(
            results,
            ScanInputs(full_name="Xiomara Quetzalcoatl", email="alice@example.com"),
        )
        assert disambiguation.is_common_name is False
        assert disambiguation.has_secondary_signals is False
        assert len(disambiguation.matched_results) == 3
        assert disambiguation.filtered_count == 0

    def test_common_name_with_signal_filters_non_matching(self):
        resolver = EntityResolver()
        results = self._results_with_and_without_signal()
        disambiguation = resolver.filter_results(
            results, ScanInputs(full_name="John Smith", email="alice@example.com")
        )
        assert disambiguation.is_common_name is True
        assert disambiguation.has_secondary_signals is True
        # Result at index 1 has no signal — should be filtered
        assert disambiguation.filtered_count == 1
        assert len(disambiguation.matched_results) == 2
        urls = [r.url for r in disambiguation.matched_results]
        assert "https://b.com" not in urls

    def test_common_name_no_signals_returns_all_unfiltered(self):
        resolver = EntityResolver()
        results = self._results_with_and_without_signal()
        disambiguation = resolver.filter_results(
            results, ScanInputs(full_name="John Smith")
        )
        assert disambiguation.is_common_name is True
        assert disambiguation.has_secondary_signals is False
        assert len(disambiguation.matched_results) == 3
        assert disambiguation.filtered_count == 0

    def test_extra_signals_used_for_filtering(self):
        resolver = EntityResolver()
        results = [
            _make_result(snippet="Works at Acme Corp", url="https://a.com"),
            _make_result(snippet="unrelated content", url="https://b.com"),
        ]
        disambiguation = resolver.filter_results(
            results,
            ScanInputs(full_name="James Brown"),
            extra_signals=["Acme Corp"],
        )
        assert disambiguation.is_common_name is True
        assert disambiguation.has_secondary_signals is True
        assert len(disambiguation.matched_results) == 1
        assert disambiguation.matched_results[0].url == "https://a.com"

    def test_empty_results_list_handled(self):
        resolver = EntityResolver()
        disambiguation = resolver.filter_results(
            [], ScanInputs(full_name="John Smith", email="j@example.com")
        )
        assert disambiguation.matched_results == []
        assert disambiguation.filtered_count == 0

    def test_returns_disambiguation_result_type(self):
        resolver = EntityResolver()
        result = resolver.filter_results([], ScanInputs())
        assert isinstance(result, DisambiguationResult)


class TestSearchModuleDisambiguation:
    """Integration tests for SearchModule._aggregate_results() with EntityResolver."""

    def _make_module_with_resolver(self, resolver: EntityResolver) -> SearchModule:
        return SearchModule(
            client=SearchClient(
                api_key="k", engine_id="e", http_client=httpx.AsyncClient()
            ),
            resolver=resolver,
        )

    def test_common_name_no_signals_produces_info_severity(self):
        resolver = EntityResolver()
        module = self._make_module_with_resolver(resolver)
        results = [_make_result(snippet="something", url="https://example.com")]
        findings = module._aggregate_results(
            results, ScanInputs(full_name="John Smith")
        )
        web_presence = next(f for f in findings if f.finding_type == "web_presence")
        assert web_presence.severity == Severity.INFO

    def test_common_name_with_email_produces_medium_severity(self):
        resolver = EntityResolver()
        module = self._make_module_with_resolver(resolver)
        results = [
            _make_result(snippet="john@example.com profile", url="https://ex.com")
        ]
        findings = module._aggregate_results(
            results, ScanInputs(full_name="John Smith", email="john@example.com")
        )
        web_presence = next(f for f in findings if f.finding_type == "web_presence")
        assert web_presence.severity == Severity.MEDIUM

    def test_uncommon_name_produces_medium_severity(self):
        resolver = EntityResolver()
        module = self._make_module_with_resolver(resolver)
        results = [_make_result(snippet="rare name info")]
        findings = module._aggregate_results(
            results, ScanInputs(full_name="Xiomara Quetzalcoatl")
        )
        web_presence = next(f for f in findings if f.finding_type == "web_presence")
        assert web_presence.severity == Severity.MEDIUM

    def test_filtered_count_reflected_in_evidence(self):
        resolver = EntityResolver()
        module = self._make_module_with_resolver(resolver)
        results = [
            _make_result(snippet="john@example.com", url="https://a.com"),
            _make_result(snippet="unrelated", url="https://b.com"),
        ]
        findings = module._aggregate_results(
            results, ScanInputs(full_name="John Smith", email="john@example.com")
        )
        web_presence = next(f for f in findings if f.finding_type == "web_presence")
        assert web_presence.evidence["filtered_count"] == 1
        assert web_presence.evidence["is_common_name"] is True

    def test_empty_results_returns_empty_findings(self):
        resolver = EntityResolver()
        module = self._make_module_with_resolver(resolver)
        findings = module._aggregate_results([], ScanInputs(full_name="John Smith"))
        assert findings == []

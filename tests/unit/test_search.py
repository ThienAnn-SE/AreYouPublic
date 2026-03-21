"""Unit tests for the Search module (T3.1).

Tests cover:
  - Query construction (_build_queries, Option A strategy)
  - Result categorization (all 6 types)
  - DataBrokerDetector (domain lookup, opt-out URL retrieval)
  - SearchClient: success path, empty results, 429 retry, 403 quota, 5xx error
  - SearchModule.execute(): full success, quota failure, missing config,
    no inputs, entity disambiguation (name-only → INFO severity)
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from piea.modules.base import ScanInputs, Severity
from piea.modules.search import (
    GOOGLE_CSE_BASE,
    DataBrokerDetector,
    ResultCategorizer,
    SearchAPIError,
    SearchClient,
    SearchModule,
    SearchQuotaError,
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
            ScanInputs(full_name="Alice", email="alice@example.com", username="alice123")
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

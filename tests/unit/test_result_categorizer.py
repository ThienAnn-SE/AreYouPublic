"""Unit tests for ResultCategorizer (T3.2).

Tests the 4-tier categorization strategy:
  Tier 1 — exact domain match (confidence 1.0)
  Tier 2 — domain suffix match (confidence 0.9)
  Tier 3 — URL path keyword match (confidence 0.7)
  Tier 4 — snippet keyword match (confidence 0.5)
  Fallback — uncategorized (confidence 0.0)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from piea.modules.categorizer import (
    ResultCategorizer,
    ResultCategory,
)
from piea.modules.search import SearchHit

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "search_categories.json"


@pytest.fixture()
def categorizer() -> ResultCategorizer:
    """Categorizer loaded from the real project config."""
    return ResultCategorizer(config_path=CONFIG_PATH)


def _hit(
    url: str = "https://example.com",
    title: str = "Example",
    snippet: str = "",
    display_link: str = "",
) -> SearchHit:
    """Helper to build a SearchHit with defaults."""
    if not display_link:
        from urllib.parse import urlparse

        display_link = urlparse(url).hostname or "example.com"
    return SearchHit(title=title, snippet=snippet, url=url, display_link=display_link)


# ---------------------------------------------------------------------------
# Tier 1 — exact domain match (confidence 1.0)
# ---------------------------------------------------------------------------


class TestExactDomainMatch:
    """Exact domain matches should return confidence 1.0."""

    def test_social_twitter(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://twitter.com/alice", display_link="twitter.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 1.0
        assert result.match_reason == "domain_exact"

    def test_social_reddit(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://www.reddit.com/u/alice", display_link="www.reddit.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 1.0

    def test_news_nytimes(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://nytimes.com/article/123", display_link="nytimes.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.NEWS
        assert result.confidence == 1.0
        assert result.match_reason == "domain_exact"

    def test_news_techcrunch(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://techcrunch.com/story/x", display_link="techcrunch.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.NEWS

    def test_professional_linkedin(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://linkedin.com/in/alice", display_link="linkedin.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.PROFESSIONAL
        assert result.confidence == 1.0

    def test_professional_github(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://github.com/alice", display_link="github.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.PROFESSIONAL

    def test_forum_quora(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://quora.com/question/123", display_link="quora.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.FORUM
        assert result.confidence == 1.0

    def test_forum_hackernews(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://news.ycombinator.com/item?id=123",
            display_link="news.ycombinator.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.FORUM

    def test_data_broker_spokeo(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://spokeo.com/alice-smith", display_link="spokeo.com")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.DATA_BROKER
        assert result.confidence == 1.0

    def test_data_broker_whitepages(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://whitepages.com/name/alice", display_link="whitepages.com"
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.DATA_BROKER

    def test_www_prefix_stripped(self, categorizer: ResultCategorizer) -> None:
        """www. prefix should be stripped before matching."""
        hit = _hit(
            url="https://www.linkedin.com/in/alice", display_link="www.linkedin.com"
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.PROFESSIONAL
        assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# Tier 2 — domain suffix match (confidence 0.9)
# ---------------------------------------------------------------------------


class TestDomainSuffixMatch:
    """Domain suffix matches should return confidence 0.9."""

    def test_mastodon_instance_social_suffix(
        self, categorizer: ResultCategorizer
    ) -> None:
        hit = _hit(
            url="https://infosec.social/@alice",
            display_link="infosec.social",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 0.9
        assert result.match_reason == "domain_suffix"

    def test_mastodon_masto_host_suffix(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://example.masto.host/@alice",
            display_link="example.masto.host",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# Tier 3 — URL path keyword match (confidence 0.7)
# ---------------------------------------------------------------------------


class TestURLKeywordMatch:
    """URL keyword matches should return confidence 0.7."""

    def test_url_with_profile_path(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://unknownsite.com/profile/alice",
            display_link="unknownsite.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 0.7
        assert result.match_reason == "keyword_url"

    def test_url_with_forum_path(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://unknownsite.com/forum/thread/123",
            display_link="unknownsite.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.FORUM
        assert result.confidence == 0.7

    def test_url_with_article_path(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://unknownsite.com/article/new-discovery",
            display_link="unknownsite.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.NEWS
        assert result.confidence == 0.7

    def test_url_with_people_search_path(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://unknownbroker.com/people/alice-smith",
            display_link="unknownbroker.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.DATA_BROKER
        assert result.confidence == 0.7


# ---------------------------------------------------------------------------
# Tier 4 — snippet keyword match (confidence 0.5)
# ---------------------------------------------------------------------------


class TestSnippetKeywordMatch:
    """Snippet keyword matches should return confidence 0.5."""

    def test_snippet_with_follower_keyword(
        self, categorizer: ResultCategorizer
    ) -> None:
        hit = _hit(
            url="https://unknownsite.com/alice",
            snippet="Alice has 500 follower on this platform",
            display_link="unknownsite.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 0.5
        assert result.match_reason == "keyword_snippet"

    def test_snippet_with_discussion_keyword(
        self, categorizer: ResultCategorizer
    ) -> None:
        hit = _hit(
            url="https://unknownsite.com/alice",
            snippet="Join the discussion about Python best practices",
            display_link="unknownsite.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.FORUM
        assert result.confidence == 0.5

    def test_snippet_with_background_check_keyword(
        self, categorizer: ResultCategorizer
    ) -> None:
        hit = _hit(
            url="https://unknownsite.com/alice",
            snippet="Run a background check on anyone instantly",
            display_link="unknownsite.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.DATA_BROKER
        assert result.confidence == 0.5

    def test_snippet_keywords_case_insensitive(
        self, categorizer: ResultCategorizer
    ) -> None:
        hit = _hit(
            url="https://unknownsite.com/alice",
            snippet="PUBLISHED yesterday in the newspaper",
            display_link="unknownsite.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.NEWS
        assert result.confidence == 0.5


# ---------------------------------------------------------------------------
# Fallback — uncategorized (confidence 0.0)
# ---------------------------------------------------------------------------


class TestUncategorized:
    """Unknown domains with no keyword matches should be uncategorized."""

    def test_unknown_domain_no_keywords(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(
            url="https://example.org/page",
            snippet="Some generic content about gardening",
            display_link="example.org",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.UNCATEGORIZED
        assert result.confidence == 0.0
        assert result.match_reason == "default"

    def test_empty_snippet(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://example.org", snippet="", display_link="example.org")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.UNCATEGORIZED


# ---------------------------------------------------------------------------
# Tier priority — higher tier wins over lower tier
# ---------------------------------------------------------------------------


class TestTierPriority:
    """Exact domain match should take priority over keyword matches."""

    def test_domain_wins_over_url_keyword(self, categorizer: ResultCategorizer) -> None:
        """reddit.com is social (domain exact), even with /comments/ in URL (forum keyword)."""
        hit = _hit(
            url="https://reddit.com/r/python/comments/abc/hello",
            display_link="reddit.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 1.0
        assert result.match_reason == "domain_exact"

    def test_domain_wins_over_snippet_keyword(
        self, categorizer: ResultCategorizer
    ) -> None:
        """github.com is professional (domain exact), even with 'follower' in snippet."""
        hit = _hit(
            url="https://github.com/alice",
            snippet="alice has 200 follower",
            display_link="github.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.PROFESSIONAL
        assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# Batch categorization
# ---------------------------------------------------------------------------


class TestBatchCategorization:
    """categorize_batch should process multiple hits."""

    def test_batch_returns_all_results(self, categorizer: ResultCategorizer) -> None:
        hits = [
            _hit(url="https://twitter.com/alice", display_link="twitter.com"),
            _hit(url="https://linkedin.com/in/alice", display_link="linkedin.com"),
            _hit(url="https://example.org/page", display_link="example.org"),
        ]
        results = categorizer.categorize_batch(hits)
        assert len(results) == 3
        assert results[0].category == ResultCategory.SOCIAL
        assert results[1].category == ResultCategory.PROFESSIONAL
        assert results[2].category == ResultCategory.UNCATEGORIZED

    def test_batch_empty_list(self, categorizer: ResultCategorizer) -> None:
        results = categorizer.categorize_batch([])
        assert results == []


# ---------------------------------------------------------------------------
# CategorizedResult dataclass
# ---------------------------------------------------------------------------


class TestCategorizedResult:
    """CategorizedResult should be frozen and contain expected fields."""

    def test_frozen(self, categorizer: ResultCategorizer) -> None:
        hit = _hit(url="https://twitter.com/alice", display_link="twitter.com")
        result = categorizer.categorize(hit)
        with pytest.raises(AttributeError):
            result.category = ResultCategory.NEWS  # type: ignore[misc]

    def test_result_preserves_original_hit(
        self, categorizer: ResultCategorizer
    ) -> None:
        hit = _hit(url="https://twitter.com/alice", display_link="twitter.com")
        result = categorizer.categorize(hit)
        assert result.result is hit


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestConfigLoading:
    """Config loading and error handling."""

    def test_loads_from_custom_path(self, tmp_path: Path) -> None:
        config = {
            "categories": {
                "social": {
                    "domains": ["custom-social.com"],
                    "domain_suffixes": [],
                    "url_keywords": [],
                    "snippet_keywords": [],
                }
            }
        }
        config_file = tmp_path / "custom.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        cat = ResultCategorizer(config_path=config_file)
        hit = _hit(
            url="https://custom-social.com/alice", display_link="custom-social.com"
        )
        result = cat.categorize(hit)
        assert result.category == ResultCategory.SOCIAL

    def test_missing_config_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            ResultCategorizer(config_path=Path("/nonexistent/config.json"))

    def test_unknown_category_in_config_skipped(self, tmp_path: Path) -> None:
        config = {
            "categories": {
                "alien_category": {
                    "domains": ["aliens.com"],
                    "domain_suffixes": [],
                    "url_keywords": [],
                    "snippet_keywords": [],
                },
                "social": {
                    "domains": ["twitter.com"],
                    "domain_suffixes": [],
                    "url_keywords": [],
                    "snippet_keywords": [],
                },
            }
        }
        config_file = tmp_path / "partial.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        cat = ResultCategorizer(config_path=config_file)
        # aliens.com should not match any valid category
        hit = _hit(url="https://aliens.com/page", display_link="aliens.com")
        result = cat.categorize(hit)
        assert result.category == ResultCategory.UNCATEGORIZED

    def test_empty_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.json"
        config_file.write_text('{"categories": {}}', encoding="utf-8")
        cat = ResultCategorizer(config_path=config_file)
        hit = _hit(url="https://twitter.com/alice", display_link="twitter.com")
        result = cat.categorize(hit)
        assert result.category == ResultCategory.UNCATEGORIZED


# ---------------------------------------------------------------------------
# Domain extraction edge cases
# ---------------------------------------------------------------------------


class TestDomainExtraction:
    """Edge cases in domain extraction."""

    def test_subdomain_stripped_to_registered(
        self, categorizer: ResultCategorizer
    ) -> None:
        """blog.twitter.com should still match twitter.com."""
        hit = _hit(
            url="https://blog.twitter.com/post/123", display_link="blog.twitter.com"
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL
        assert result.confidence == 1.0

    def test_display_link_preferred_over_url(
        self, categorizer: ResultCategorizer
    ) -> None:
        """display_link is the primary domain source."""
        hit = _hit(
            url="https://redirector.example.com/goto?url=twitter.com",
            display_link="twitter.com",
        )
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.SOCIAL

    def test_empty_display_link_falls_back_to_url(
        self, categorizer: ResultCategorizer
    ) -> None:
        hit = _hit(url="https://linkedin.com/in/alice", display_link="")
        result = categorizer.categorize(hit)
        assert result.category == ResultCategory.PROFESSIONAL

"""Search result categorizer for PIEA.

Categorizes search hits into semantic categories (social, news,
professional, forum, data_broker, uncategorized) using a tiered
matching strategy: exact domain → domain suffix → URL keywords →
snippet keywords.

Config-driven: all domain mappings and keyword patterns live in
``config/search_categories.json`` and can be updated without code
changes.

Requirements: FR-5.1 (result categorization)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from piea.modules.search import SearchHit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES_CONFIG_PATH = Path("config/search_categories.json")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ResultCategory(StrEnum):
    """Semantic category for a search result."""

    SOCIAL = "social"
    NEWS = "news"
    PROFESSIONAL = "professional"
    FORUM = "forum"
    DATA_BROKER = "data_broker"
    UNCATEGORIZED = "uncategorized"


@dataclass(frozen=True, slots=True)
class CategorizedResult:
    """A search hit with an assigned category and confidence score.

    Attributes:
        result: The original search hit being categorized.
        category: The assigned semantic category.
        confidence: Confidence score from 0.0 to 1.0 reflecting match quality.
        match_reason: How the category was determined (domain_exact,
            domain_suffix, keyword_url, keyword_snippet, default).
    """

    result: SearchHit
    category: ResultCategory
    confidence: float
    match_reason: str


# ---------------------------------------------------------------------------
# Internal config structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _CategoryRule:
    """Parsed rules for one category from config JSON."""

    category: ResultCategory
    domains: frozenset[str]
    domain_suffixes: tuple[str, ...]
    url_keywords: tuple[str, ...]
    snippet_patterns: tuple[re.Pattern[str], ...]


# ---------------------------------------------------------------------------
# ResultCategorizer
# ---------------------------------------------------------------------------


class ResultCategorizer:
    """Categorize :class:`SearchHit` instances into semantic categories.

    Uses a tiered matching strategy with decreasing confidence:

    1. **Exact domain match** (confidence 1.0) — the hit's registered
       domain appears in the category's ``domains`` list.
    2. **Domain suffix match** (confidence 0.9) — the hit's domain ends
       with one of the category's ``domain_suffixes``.
    3. **URL path keyword match** (confidence 0.7) — the hit's URL path
       contains one of the category's ``url_keywords``.
    4. **Snippet keyword match** (confidence 0.5) — the hit's snippet
       text contains one of the category's ``snippet_keywords``.

    The first tier that produces a match wins.  If no tier matches,
    the result is assigned ``ResultCategory.UNCATEGORIZED`` with
    confidence 0.0.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or DEFAULT_CATEGORIES_CONFIG_PATH
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self._rules = self._parse_config(raw)

    # -- public API ---------------------------------------------------------

    def categorize(self, hit: SearchHit) -> CategorizedResult:
        """Assign a category to a single search hit.

        Tries each tier in order; returns the first match.
        """
        return (
            self._match_exact_domain(hit)
            or self._match_domain_suffix(hit)
            or self._match_url_keyword(hit)
            or self._match_snippet_keyword(hit)
            or CategorizedResult(
                result=hit,
                category=ResultCategory.UNCATEGORIZED,
                confidence=0.0,
                match_reason="default",
            )
        )

    def _match_exact_domain(self, hit: SearchHit) -> CategorizedResult | None:
        """Tier 1 — exact domain match (confidence 1.0)."""
        full_domain = self._normalize_domain(hit.display_link, hit.url)
        registered_domain = self._extract_registered_domain(hit.url, hit.display_link)
        for rule in self._rules:
            if full_domain in rule.domains or registered_domain in rule.domains:
                return CategorizedResult(
                    result=hit,
                    category=rule.category,
                    confidence=1.0,
                    match_reason="domain_exact",
                )
        return None

    def _match_domain_suffix(self, hit: SearchHit) -> CategorizedResult | None:
        """Tier 2 — domain suffix match (confidence 0.9)."""
        display_lower = hit.display_link.lower()
        for rule in self._rules:
            for suffix in rule.domain_suffixes:
                if display_lower.endswith(suffix):
                    return CategorizedResult(
                        result=hit,
                        category=rule.category,
                        confidence=0.9,
                        match_reason="domain_suffix",
                    )
        return None

    def _match_url_keyword(self, hit: SearchHit) -> CategorizedResult | None:
        """Tier 3 — URL path keyword match (confidence 0.7)."""
        url_path = urlparse(hit.url).path.lower()
        for rule in self._rules:
            for keyword in rule.url_keywords:
                if keyword in url_path:
                    return CategorizedResult(
                        result=hit,
                        category=rule.category,
                        confidence=0.7,
                        match_reason="keyword_url",
                    )
        return None

    def _match_snippet_keyword(self, hit: SearchHit) -> CategorizedResult | None:
        """Tier 4 — snippet keyword match (confidence 0.5)."""
        snippet_lower = hit.snippet.lower()
        for rule in self._rules:
            for pattern in rule.snippet_patterns:
                if pattern.search(snippet_lower):
                    return CategorizedResult(
                        result=hit,
                        category=rule.category,
                        confidence=0.5,
                        match_reason="keyword_snippet",
                    )
        return None

    def categorize_batch(self, hits: list[SearchHit]) -> list[CategorizedResult]:
        """Categorize a list of search hits."""
        return [self.categorize(hit) for hit in hits]

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _normalize_domain(display_link: str, url: str) -> str:
        """Normalize a domain by stripping www. prefix only.

        Preserves subdomains like ``news.ycombinator.com`` which may
        appear as distinct entries in the config.
        """
        raw = display_link or urlparse(url).hostname or ""
        return raw.lower().removeprefix("www.")

    @staticmethod
    def _extract_registered_domain(url: str, display_link: str) -> str:
        """Extract the registered domain from a URL or display_link.

        Prefers ``display_link`` (already provided by Google CSE as the
        registered domain).  Falls back to parsing the URL hostname.
        Strips ``www.`` prefix and keeps the last two domain parts.
        """
        raw = display_link or urlparse(url).hostname or ""
        raw = raw.lower().removeprefix("www.")
        parts = raw.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return raw

    @staticmethod
    def _parse_config(raw: dict[str, Any]) -> tuple[_CategoryRule, ...]:
        """Parse the JSON config into internal rule objects."""
        categories_raw: dict[str, Any] = raw.get("categories", {})
        rules: list[_CategoryRule] = []

        for cat_name, cat_config in categories_raw.items():
            try:
                category = ResultCategory(cat_name)
            except ValueError:
                logger.warning("Skipping unknown category in config: %s", cat_name)
                continue

            snippet_keywords: list[str] = cat_config.get("snippet_keywords", [])
            snippet_patterns = tuple(
                re.compile(re.escape(kw)) for kw in snippet_keywords
            )

            rules.append(
                _CategoryRule(
                    category=category,
                    domains=frozenset(cat_config.get("domains", [])),
                    domain_suffixes=tuple(cat_config.get("domain_suffixes", [])),
                    url_keywords=tuple(cat_config.get("url_keywords", [])),
                    snippet_patterns=snippet_patterns,
                )
            )

        return tuple(rules)

"""Google Custom Search Engine integration module.

Queries Google CSE for publicly visible mentions of a target identity,
classifies each result into one of six categories, and flags data broker
listings as high-severity findings.

Google CSE API docs: https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from piea.config import settings
from piea.modules.base import (
    BaseModule,
    ModuleFinding,
    ModuleResult,
    ScanInputs,
    Severity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOOGLE_CSE_BASE = "https://www.googleapis.com/customsearch/v1"
USER_AGENT = "PIEA-SecurityScanner/1.0"

# Small delay between requests to stay within Google CSE's per-second quota.
REQUEST_INTERVAL_SECONDS = 0.5

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 30.0

# ---------------------------------------------------------------------------
# Domain classification sets
# ---------------------------------------------------------------------------

_SOCIAL_DOMAINS: frozenset[str] = frozenset(
    {
        "linkedin.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "instagram.com",
        "github.com",
        "gitlab.com",
        "tiktok.com",
        "pinterest.com",
        "tumblr.com",
        "youtube.com",
        "vimeo.com",
        "flickr.com",
        "snapchat.com",
        "mastodon.social",
    }
)

_PROFESSIONAL_DOMAINS: frozenset[str] = frozenset(
    {
        "xing.com",
        "glassdoor.com",
        "crunchbase.com",
        "angel.co",
        "wellfound.com",
        "researchgate.net",
        "academia.edu",
        "orcid.org",
        "meetup.com",
    }
)

_FORUM_DOMAINS: frozenset[str] = frozenset(
    {
        "reddit.com",
        "stackoverflow.com",
        "quora.com",
        "news.ycombinator.com",
        "medium.com",
        "dev.to",
        "hashnode.com",
        "lobste.rs",
        "slashdot.org",
        "disqus.com",
    }
)

_NEWS_DOMAINS: frozenset[str] = frozenset(
    {
        "nytimes.com",
        "bbc.com",
        "bbc.co.uk",
        "reuters.com",
        "cnn.com",
        "theguardian.com",
        "washingtonpost.com",
        "apnews.com",
        "bloomberg.com",
        "techcrunch.com",
        "wired.com",
        "arstechnica.com",
        "theverge.com",
        "forbes.com",
        "businessinsider.com",
    }
)

# ---------------------------------------------------------------------------
# Data broker lists (FR-5.2: minimum 20 domains)
# ---------------------------------------------------------------------------

_DATA_BROKER_DOMAINS: frozenset[str] = frozenset(
    {
        "spokeo.com",
        "whitepages.com",
        "peoplefinder.com",
        "beenverified.com",
        "intelius.com",
        "zabasearch.com",
        "pipl.com",
        "peekyou.com",
        "radaris.com",
        "instantcheckmate.com",
        "truthfinder.com",
        "mylife.com",
        "peoplesmart.com",
        "checkpeople.com",
        "familytreenow.com",
        "usphonebook.com",
        "publicrecordsnow.com",
        "fastpeoplesearch.com",
        "addresses.com",
        "anywho.com",
        "peoplecrawler.com",
        "phonebook.com",
        "vericora.com",
        "clustrmaps.com",
    }
)

_DATA_BROKER_OPT_OUT: dict[str, str] = {
    "spokeo.com": "https://www.spokeo.com/optout",
    "whitepages.com": "https://www.whitepages.com/suppression-requests",
    "peoplefinder.com": "https://www.peoplefinder.com/optout.php",
    "beenverified.com": "https://www.beenverified.com/faq/opt-out/",
    "intelius.com": "https://www.intelius.com/opt-out/",
    "radaris.com": "https://radaris.com/control/privacy",
    "instantcheckmate.com": "https://www.instantcheckmate.com/opt-out/",
    "truthfinder.com": "https://www.truthfinder.com/opt-out/",
    "mylife.com": "https://www.mylife.com/privacy-policy/index.pubview",
    "fastpeoplesearch.com": "https://www.fastpeoplesearch.com/removal",
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SearchModuleError(Exception):
    """Base exception for search module errors."""


class SearchAPIError(SearchModuleError):
    """Raised when the Google CSE API returns an unexpected HTTP error.

    Attributes:
        status_code: The HTTP status code returned by the API.
    """

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Google CSE API returned HTTP {status_code}")


class SearchQuotaError(SearchModuleError):
    """Raised when Google CSE quota is exhausted or rate limit is hit."""

    def __init__(self) -> None:
        super().__init__("Google CSE quota exceeded or rate limit hit after retries")


# ---------------------------------------------------------------------------
# Search result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single result returned by the Google Custom Search API.

    Attributes:
        title: Page title.
        snippet: Short content excerpt from the result page.
        url: Canonical URL of the result.
        display_link: Human-readable domain shown in search results.
        category: Classified result type (one of six fixed strings):
            social_profile, news_mention, professional_directory,
            forum_post, data_broker, uncategorized.
        is_data_broker: True if the domain is a known data broker.
        opt_out_url: Data broker removal URL, if known.
    """

    title: str
    snippet: str
    url: str
    display_link: str
    category: str
    is_data_broker: bool
    opt_out_url: str | None


# ---------------------------------------------------------------------------
# DataBrokerDetector
# ---------------------------------------------------------------------------


class DataBrokerDetector:
    """Identifies data broker domains and maps them to opt-out URLs.

    Uses frozen sets for O(1) domain lookup.

    Class attributes:
        DATA_BROKER_DOMAINS: Frozenset of known data broker apex domains.
        DATA_BROKER_OPT_OUT: Mapping of broker domain to its opt-out URL.
    """

    DATA_BROKER_DOMAINS: frozenset[str] = _DATA_BROKER_DOMAINS
    DATA_BROKER_OPT_OUT: dict[str, str] = _DATA_BROKER_OPT_OUT

    def is_data_broker(self, url: str) -> bool:
        """Return True if the URL belongs to a known data broker domain.

        Args:
            url: The full URL to classify.

        Returns:
            True if the domain (or any subdomain) is a known data broker.
        """
        domain = _extract_domain(url)
        return domain in self.DATA_BROKER_DOMAINS or any(
            domain.endswith(f".{d}") for d in self.DATA_BROKER_DOMAINS
        )

    def get_opt_out_url(self, url: str) -> str | None:
        """Return the opt-out URL for the data broker at the given URL.

        Args:
            url: The full URL of the data broker result.

        Returns:
            Opt-out URL string, or None if no mapping exists for this broker.
        """
        domain = _extract_domain(url)
        if domain in self.DATA_BROKER_OPT_OUT:
            return self.DATA_BROKER_OPT_OUT[domain]
        for broker_domain, opt_out in self.DATA_BROKER_OPT_OUT.items():
            if domain.endswith(f".{broker_domain}"):
                return opt_out
        return None


# ---------------------------------------------------------------------------
# ResultCategorizer
# ---------------------------------------------------------------------------


class ResultCategorizer:
    """Classifies search result URLs into one of six predefined categories.

    Classification order (first match wins):
        1. data_broker           — known data broker domain
        2. social_profile        — major social network
        3. forum_post            — forum or community platform
        4. professional_directory — professional/academic network
        5. news_mention          — news publication
        6. uncategorized         — no match

    Args:
        detector: DataBrokerDetector instance used for broker classification.
    """

    def __init__(self, detector: DataBrokerDetector) -> None:
        self._detector = detector

    def classify(self, url: str) -> str:
        """Classify a URL into one of the six category strings.

        Args:
            url: The full URL of the search result.

        Returns:
            One of: "data_broker", "social_profile", "forum_post",
            "professional_directory", "news_mention", "uncategorized".
        """
        if self._detector.is_data_broker(url):
            return "data_broker"
        domain = _extract_domain(url)
        if _domain_matches(domain, _SOCIAL_DOMAINS):
            return "social_profile"
        if _domain_matches(domain, _FORUM_DOMAINS):
            return "forum_post"
        if _domain_matches(domain, _PROFESSIONAL_DOMAINS):
            return "professional_directory"
        if _domain_matches(domain, _NEWS_DOMAINS):
            return "news_mention"
        return "uncategorized"


# ---------------------------------------------------------------------------
# SearchClient
# ---------------------------------------------------------------------------


class SearchClient:
    """Async client for the Google Custom Search JSON API.

    Handles authentication, rate limiting, retries with exponential backoff,
    and response parsing. One instance should be shared across a scan.

    Args:
        api_key: Google CSE API key (NFR-S1: must come from env, not source).
        engine_id: Google Custom Search Engine ID.
        http_client: Optional pre-configured httpx.AsyncClient. If not
            provided, one will be created (and must be closed via close()).
    """

    def __init__(
        self,
        api_key: str,
        engine_id: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._engine_id = engine_id
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        self._detector = DataBrokerDetector()
        self._categorizer = ResultCategorizer(self._detector)
        # Semaphore enforces one in-flight request at a time to respect rate limits.
        self._rate_semaphore = asyncio.Semaphore(1)

    async def search(self, query: str) -> list[SearchResult]:
        """Execute a single search query against Google CSE.

        Args:
            query: The search query string. Never logged verbatim (may
                contain user-supplied PII in quoted form).

        Returns:
            List of SearchResult objects. Empty list if no results found.

        Raises:
            SearchQuotaError: If the API returns 403 (quota) or exhausts
                retries on 429 (rate limit).
            SearchAPIError: If the API returns an unexpected non-429/403 error.
            SearchModuleError: If the request times out.
        """
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(1, MAX_RETRIES + 1):
            async with self._rate_semaphore:
                try:
                    response = await self._client.get(
                        GOOGLE_CSE_BASE,
                        params={
                            "key": self._api_key,
                            "cx": self._engine_id,
                            "q": query,
                        },
                    )
                except httpx.TimeoutException as exc:
                    raise SearchModuleError("Search request timed out") from exc
                finally:
                    # L009: sleep in finally to enforce rate limit even on exception,
                    # preventing the semaphore release from immediately allowing
                    # another request before the interval has elapsed.
                    await asyncio.sleep(REQUEST_INTERVAL_SECONDS)

            if response.status_code == 403:
                raise SearchQuotaError()
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", str(backoff)))
                logger.warning(
                    "Search rate limited (attempt %d/%d), waiting %.1fs",
                    attempt,
                    MAX_RETRIES,
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # L007: re-raise without the raw response URL, which contains
                # the API key and query string in its params.
                raise SearchAPIError(exc.response.status_code) from None

            return self._parse_response(response.json())

        raise SearchQuotaError()

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    def _parse_response(self, data: dict[str, Any]) -> list[SearchResult]:
        """Parse a Google CSE JSON response into SearchResult objects.

        Args:
            data: Parsed JSON response dict from the Google CSE API.
                Uses dict[str, Any] per L003 to avoid mypy .get() failures.

        Returns:
            List of SearchResult objects (empty list if no "items" key).
        """
        items: list[dict[str, Any]] = data.get("items", [])
        results: list[SearchResult] = []
        for item in items:
            url = str(item.get("link", ""))
            is_broker = self._detector.is_data_broker(url)
            results.append(
                SearchResult(
                    title=str(item.get("title", "")),
                    snippet=str(item.get("snippet", "")),
                    url=url,
                    display_link=str(item.get("displayLink", "")),
                    category=self._categorizer.classify(url),
                    is_data_broker=is_broker,
                    opt_out_url=(
                        self._detector.get_opt_out_url(url) if is_broker else None
                    ),
                )
            )
        return results


# ---------------------------------------------------------------------------
# SearchModule (BaseModule implementation)
# ---------------------------------------------------------------------------


class SearchModule(BaseModule):
    """OSINT module that queries Google CSE for public mentions of a target.

    Builds up to 3 targeted search queries (Option A strategy) from the scan
    inputs, fetches results from Google Custom Search JSON API, classifies each
    result, and flags data broker listings as HIGH severity findings.

    Option A query strategy:
        Q1: '"{name}"'                                    — broad name search
        Q2: '"{name}" site:linkedin.com OR site:twitter.com' — social profiles
        Q3: '"{email}" OR "{username}"'                   — secondary identifiers

    Args:
        client: Optional pre-built SearchClient. If not provided, one will be
            constructed from settings.google_cse_api_key / google_cse_engine_id.
    """

    def __init__(self, client: SearchClient | None = None) -> None:
        self._client = client or SearchClient(
            api_key=settings.google_cse_api_key,
            engine_id=settings.google_cse_engine_id,
        )

    @property
    def name(self) -> str:
        return "search"

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Run Google CSE search for the given scan inputs.

        Returns ModuleResult(success=False) for config errors or API failures
        rather than raising, per NFR-R1 graceful degradation requirement.

        Args:
            inputs: Scan seed data (email, username, full name).

        Returns:
            ModuleResult containing data broker findings, a web-presence
            summary finding, and execution metadata.
        """
        if not settings.google_cse_api_key or not settings.google_cse_engine_id:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["Google CSE API key or Engine ID not configured"],
            )

        queries = self._build_queries(inputs)
        if not queries:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["No usable inputs provided to build search queries"],
            )

        all_results: list[SearchResult] = []
        errors: list[str] = []

        for query in queries:
            try:
                results = await self._client.search(query)
                all_results.extend(results)
            except SearchQuotaError as exc:
                logger.warning("Search quota exhausted: %s", exc)
                errors.append(str(exc))
                break  # quota gone — remaining queries will also fail
            except SearchModuleError as exc:
                logger.warning("Search query failed: %s", exc)
                errors.append(str(exc))

        findings = self._aggregate_results(all_results, inputs)
        return ModuleResult(
            module_name=self.name,
            success=not errors or bool(all_results),
            findings=findings,
            errors=errors,
            metadata={
                "total_results": len(all_results),
                "queries_executed": len(queries) - len(errors),
                "data_broker_hits": sum(1 for r in all_results if r.is_data_broker),
            },
        )

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        await self._client.close()

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _build_queries(self, inputs: ScanInputs) -> list[str]:
        """Build up to 3 search queries from available scan inputs (Option A).

        Query strategy:
            Q1: '"{name}"'     — broad name search (email/username fallback)
            Q2: '"{name}" site:linkedin.com OR site:twitter.com' — social
            Q3: '"{email}" OR "{username}"'  — secondary identifiers

        Args:
            inputs: Scan seed data.

        Returns:
            List of 1–3 non-empty query strings, or empty list if no inputs.
        """
        name = _sanitize(inputs.full_name)
        email = _sanitize(inputs.email)
        username = _sanitize(inputs.username)

        queries: list[str] = []
        primary_type: str | None = None

        # Q1: primary identifier
        if name:
            queries.append(f'"{name}"')
            primary_type = "name"
        elif email:
            queries.append(f'"{email}"')
            primary_type = "email"
        elif username:
            queries.append(f'"{username}"')
            primary_type = "username"

        # Q2: social-site-restricted name search (only when name is available)
        if name:
            queries.append(f'"{name}" site:linkedin.com OR site:twitter.com')

        # Q3: secondary identifiers (skip whichever was already used in Q1)
        secondary = [
            f'"{v}"'
            for field_type, v in [("email", email), ("username", username)]
            if v and field_type != primary_type
        ]
        if secondary:
            queries.append(" OR ".join(secondary))

        return queries[:3]

    def _aggregate_results(
        self,
        results: list[SearchResult],
        inputs: ScanInputs,
    ) -> list[ModuleFinding]:
        """Convert raw SearchResults into ModuleFindings.

        Produces one HIGH finding per unique data broker domain, plus a
        summary web-presence finding. Severity of the summary is INFO when
        only full_name is provided (entity disambiguation — low confidence
        without secondary signals like email or username).

        Args:
            results: All search results aggregated across executed queries.
            inputs: Original scan inputs used for disambiguation check.

        Returns:
            List of ModuleFinding objects (empty if results is empty).
        """
        if not results:
            return []

        findings: list[ModuleFinding] = []

        # One HIGH finding per unique data broker domain
        seen_domains: set[str] = set()
        for r in results:
            if not r.is_data_broker:
                continue
            domain = _extract_domain(r.url)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            findings.append(
                ModuleFinding(
                    finding_type="data_broker_listing",
                    severity=Severity.HIGH,
                    category="data_broker",
                    title=f"Personal data listed on {domain}",
                    description=(
                        f'Your information appears on the data broker site "{domain}". '
                        "Data brokers aggregate and sell personal records, increasing "
                        "your exposure to spam, phishing, and social engineering attacks."
                    ),
                    platform=domain,
                    evidence={
                        "url": r.url,
                        "title": r.title,
                        "snippet": r.snippet,
                    },
                    remediation_action=f"Request removal of your data from {domain}.",
                    remediation_effort="moderate",
                    remediation_url=r.opt_out_url,
                    weight=0.7,
                )
            )

        # Summary finding — severity reflects confidence in identity match
        only_name = bool(inputs.full_name) and not inputs.email and not inputs.username
        summary_severity = Severity.INFO if only_name else Severity.MEDIUM
        low_confidence_note = (
            " Confidence is low — only a name was provided with no secondary signals."
            if only_name
            else ""
        )
        findings.append(
            ModuleFinding(
                finding_type="web_presence",
                severity=summary_severity,
                category="web_presence",
                title=f"{len(results)} public web result(s) found",
                description=(
                    f"Google search returned {len(results)} result(s) for the "
                    f"provided identity.{low_confidence_note}"
                ),
                platform="google",
                evidence={
                    "total_results": len(results),
                    "category_counts": _count_categories(results),
                },
                remediation_action=(
                    "Review results and remove or limit public profiles as appropriate."
                ),
                remediation_effort="hard",
                weight=0.3 if only_name else 0.5,
            )
        )

        return findings


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_domain(url: str) -> str:
    """Extract the apex domain from a URL, stripping any www. prefix.

    Args:
        url: Any URL string.

    Returns:
        Lowercase domain without leading 'www.', or empty string on error.
    """
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except (ValueError, AttributeError):
        return ""


def _sanitize(value: str | None) -> str:
    """Strip and sanitize a user-supplied string for safe inclusion in queries.

    Removes characters that could alter query semantics (parentheses,
    angle brackets, backslashes). Prevents query injection via user inputs.

    Args:
        value: Raw string or None.

    Returns:
        Cleaned string, or empty string if value is None or blank.
    """
    if not value:
        return ""
    return re.sub(r"[()\\<>]", "", value.strip())


def _domain_matches(domain: str, domain_set: frozenset[str]) -> bool:
    """Return True if domain is in the set or is a subdomain of any member.

    Args:
        domain: Extracted apex or subdomain to check.
        domain_set: Set of known domains to match against.

    Returns:
        True if the domain matches directly or via subdomain suffix.
    """
    return domain in domain_set or any(domain.endswith(f".{d}") for d in domain_set)


def _count_categories(results: list[SearchResult]) -> dict[str, int]:
    """Count search results grouped by category.

    Args:
        results: List of classified SearchResult objects.

    Returns:
        Dict mapping category name to its result count.
    """
    counts: dict[str, int] = {}
    for r in results:
        counts[r.category] = counts.get(r.category, 0) + 1
    return counts

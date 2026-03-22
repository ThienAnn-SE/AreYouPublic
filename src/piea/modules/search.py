"""Google Custom Search API module for PIEA.

Enumerates the public web footprint of a target identity using the
Google Custom Search JSON API, detects data broker exposure, and
returns structured ModuleFinding results.

External docs: https://developers.google.com/custom-search/v1
Requirements: FR-5.1 (web search), FR-5.2 (data broker flagging)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from piea.modules.base import (
    BaseModule,
    ModuleAPIError,
    ModuleFinding,
    ModuleResult,
    ModuleTimeoutError,
    RateLimitExceededError,
    ScanInputs,
    Severity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CSE_API_BASE = "https://www.googleapis.com/customsearch/v1"
MAX_QUERIES_PER_SCAN = 3
DEFAULT_BROKERS_CONFIG_PATH = Path("config/data_brokers.json")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A single result returned by the Google Custom Search API.

    Attributes:
        title: Page title from the search result.
        snippet: Short text excerpt shown in search results.
        url: Canonical URL of the result page.
        display_link: Registered domain shown by Google (e.g. "linkedin.com").
    """

    title: str
    snippet: str
    url: str
    display_link: str


@dataclass(frozen=True, slots=True)
class SearchQueryResult:
    """Output of a single query execution against the CSE API.

    Attributes:
        query: The query string that was submitted.
        hits: Ordered results returned for this query.
        quota_exhausted: True when the API returned HTTP 429 (daily quota hit).
    """

    query: str
    hits: tuple[SearchHit, ...]
    quota_exhausted: bool = False


# ---------------------------------------------------------------------------
# SearchClient
# ---------------------------------------------------------------------------


class SearchClient:
    """Thin async HTTP wrapper around the Google Custom Search JSON API.

    External docs: https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list
    """

    def __init__(self, api_key: str, engine_id: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._engine_id = engine_id
        self._http = httpx.AsyncClient(timeout=timeout)

    async def search(self, query: str) -> tuple[SearchHit, ...]:
        """Execute one search query and return matching hits.

        Raises:
            RateLimitExceededError: HTTP 429 — daily quota exhausted.
            ModuleAPIError: Any other 4xx/5xx response.
            ModuleTimeoutError: Request exceeded the configured timeout.
        """
        try:
            response = await self._http.get(
                CSE_API_BASE,
                params={"key": self._api_key, "cx": self._engine_id, "q": query},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ModuleTimeoutError("search", str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RateLimitExceededError("search") from exc
            raise ModuleAPIError("search", exc.response.status_code) from exc

        payload: dict[str, Any] = response.json()
        return tuple(self._parse_hit(item) for item in payload.get("items", []))

    def _parse_hit(self, item: dict[str, Any]) -> SearchHit:
        """Parse one CSE result item into a SearchHit."""
        return SearchHit(
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            url=item["link"],
            display_link=item.get("displayLink", ""),
        )

    async def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        await self._http.aclose()


# ---------------------------------------------------------------------------
# SearchModuleConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchModuleConfig:
    """Configuration for SearchModule.

    Attributes:
        api_key: Google Custom Search API key.
        engine_id: Google Custom Search Engine ID.
        brokers_config_path: Path to data broker registry JSON.
        timeout: HTTP request timeout in seconds.
    """

    api_key: str
    engine_id: str
    brokers_config_path: Path = DEFAULT_BROKERS_CONFIG_PATH
    timeout: float = 10.0


# ---------------------------------------------------------------------------
# SearchModule
# ---------------------------------------------------------------------------


class SearchModule(BaseModule):
    """OSINT module: enumerates public search footprint via Google CSE."""

    def __init__(self, config: SearchModuleConfig) -> None:
        self._client = SearchClient(
            api_key=config.api_key, engine_id=config.engine_id, timeout=config.timeout
        )
        broker_data = json.loads(config.brokers_config_path.read_text(encoding="utf-8"))
        brokers = broker_data["brokers"]
        self._broker_domains: frozenset[str] = frozenset(
            entry["domain"] for entry in brokers
        )
        self._broker_optout: dict[str, str] = {
            entry["domain"]: entry["optout_url"] for entry in brokers
        }

    @property
    def name(self) -> str:
        return "search"

    def _build_queries(self, inputs: ScanInputs) -> list[str]:
        """Build up to MAX_QUERIES_PER_SCAN queries from available inputs."""
        candidates: list[str] = []

        if inputs.full_name:
            candidates.append(f'"{inputs.full_name}"')

        if inputs.full_name and inputs.email and "@" in inputs.email:
            email_domain = inputs.email.split("@")[1]
            candidates.append(f'"{inputs.full_name}" "@{email_domain}"')

        if inputs.username and len(candidates) < MAX_QUERIES_PER_SCAN:
            candidates.append(f'"{inputs.username}"')

        if (
            inputs.full_name
            and inputs.username
            and len(candidates) < MAX_QUERIES_PER_SCAN
        ):
            candidates.append(f'"{inputs.full_name}" "{inputs.username}"')

        return list(dict.fromkeys(candidates))[:MAX_QUERIES_PER_SCAN]

    def _is_broker(self, hit: SearchHit) -> bool:
        """Return True if the hit's domain is in the known data broker registry."""
        domain = hit.display_link.lower().removeprefix("www.")
        parts = domain.split(".")
        registered = ".".join(parts[-2:])
        return registered in self._broker_domains

    def _get_optout_url(self, registered_domain: str) -> str:
        """Return the opt-out URL for a broker domain, or a fallback."""
        return self._broker_optout.get(
            registered_domain, f"https://{registered_domain}"
        )

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Enumerate public search footprint and detect data broker exposure."""
        queries = self._build_queries(inputs)
        if not queries:
            return ModuleResult(module_name=self.name, success=True)

        deduplicated: dict[str, SearchHit] = {}
        errors: list[str] = []
        quota_exhausted = False

        for query in queries:
            try:
                hits = await self._client.search(query)
            except RateLimitExceededError:
                errors.append("Google CSE daily quota exhausted — partial results only")
                quota_exhausted = True
                break
            except (ModuleAPIError, ModuleTimeoutError) as exc:
                errors.append(str(exc))
                continue

            for hit in hits:
                if hit.url not in deduplicated:
                    deduplicated[hit.url] = hit

        findings = self._build_findings(
            hits=list(deduplicated.values()),
            inputs=inputs,
            queries_used=queries,
        )
        return ModuleResult(
            module_name=self.name,
            success=not quota_exhausted,
            findings=findings,
            errors=errors,
        )

    def _build_findings(
        self,
        hits: list[SearchHit],
        inputs: ScanInputs,
        queries_used: list[str],
    ) -> list[ModuleFinding]:
        """Generate all ModuleFindings from deduplicated search hits."""
        findings: list[ModuleFinding] = []
        if hits:
            findings.append(self._build_exposure_finding(hits, queries_used, inputs))
        for hit in hits:
            if self._is_broker(hit):
                findings.append(self._build_broker_finding(hit))
        return findings

    def _build_exposure_finding(
        self,
        hits: list[SearchHit],
        queries_used: list[str],
        inputs: ScanInputs,
    ) -> ModuleFinding:
        """Build the search_exposure finding summarising all results."""
        result_count = len(hits)
        if result_count <= 3:
            severity = Severity.LOW
        elif result_count <= 10:
            severity = Severity.MEDIUM
        else:
            severity = Severity.HIGH

        identifier = inputs.full_name or inputs.username or inputs.email or "target"
        evidence: dict[str, Any] = {
            "query_count": len(queries_used),
            "result_count": result_count,
            "urls": [h.url for h in hits[:10]],
            "queries_used": queries_used,
        }
        return ModuleFinding(
            finding_type="search_exposure",
            severity=severity,
            category="search",
            title=f"Public search results found for {identifier}",
            description=(
                f"Found {result_count} public web result(s) for the target identity. "
                "Results indicate public exposure on the web."
            ),
            platform=None,
            evidence=evidence,
            remediation_action="Review results and remove or restrict public profiles where possible.",
            remediation_effort="moderate",
        )

    def _build_broker_finding(self, hit: SearchHit) -> ModuleFinding:
        """Build a data_broker_exposure finding for one matched broker hit."""
        domain = hit.display_link.lower().removeprefix("www.")
        parts = domain.split(".")
        registered = ".".join(parts[-2:])
        optout_url = self._get_optout_url(registered)
        evidence: dict[str, Any] = {
            "url": hit.url,
            "title": hit.title,
            "snippet": hit.snippet,
            "broker_domain": registered,
        }
        return ModuleFinding(
            finding_type="data_broker_exposure",
            severity=Severity.HIGH,
            category="search",
            title=f"Profile found on data broker: {hit.display_link}",
            description=(
                f"A profile for the target was found on the data broker site {registered}. "
                "Data brokers aggregate personal information and sell it publicly."
            ),
            platform=registered,
            evidence=evidence,
            remediation_action=f"Request removal at {optout_url}",
            remediation_effort="easy",
            remediation_url=optout_url,
        )

    async def close(self) -> None:
        await self._client.close()

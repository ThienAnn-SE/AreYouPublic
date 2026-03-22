"""Hunter.io email pattern discovery module (T3.6).

Queries two Hunter.io v2 endpoints:
  - /v2/domain-search: Retrieves the email naming pattern and known addresses
    for the organization domain extracted from the subject's email.
  - /v2/email-finder: Predicts the most likely email address for a given
    first name + last name on the domain.

The API key is passed as a query parameter; httpx.HTTPStatusError is caught
and re-raised WITHOUT the URL to prevent key leakage (L007 — URL contains
`api_key=` as plaintext).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

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

HUNTER_BASE = "https://api.hunter.io/v2"
USER_AGENT = "PIEA-SecurityScanner/1.0"

# Conservative inter-request delay — Hunter.io free tier is 25 req/month.
REQUEST_INTERVAL_SECONDS: float = 1.0

# Minimum Hunter.io confidence score to emit an email_address_confirmed finding.
EMAIL_CONFIDENCE_THRESHOLD: int = 70


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HunterError(Exception):
    """Base exception for Hunter.io module errors."""


class HunterAPIError(HunterError):
    """Raised when the Hunter.io API returns an unexpected HTTP error.

    The original httpx.HTTPStatusError is NOT chained to prevent API key
    leakage via the request URL (L007).

    Attributes:
        status_code: HTTP status code returned by the API.
    """

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Hunter.io API returned HTTP {status_code}")


class HunterTimeoutError(HunterError):
    """Raised when a Hunter.io request exceeds its timeout."""


class HunterRateLimitError(HunterError):
    """Raised when Hunter.io returns HTTP 429 (rate limit exceeded).

    Attributes:
        retry_after: Seconds to wait before retrying, or None if not provided.
    """

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Hunter.io rate limit exceeded"
        if retry_after is not None:
            msg += f" (retry after {retry_after:.0f}s)"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HunterEmailRecord:
    """A single email address record returned by Hunter.io domain search.

    Attributes:
        value: The email address string.
        email_type: ``"personal"`` or ``"generic"``.
        confidence: Hunter.io confidence score (0–100).
        first_name: Inferred first name, or None.
        last_name: Inferred last name, or None.
    """

    value: str
    email_type: str
    confidence: int
    first_name: str | None
    last_name: str | None


@dataclass(frozen=True, slots=True)
class HunterDomainResult:
    """Parsed response from the Hunter.io domain-search endpoint.

    Attributes:
        domain: The queried domain.
        pattern: Email naming pattern (e.g. ``"{first}.{last}"``), or None.
        emails: List of known email records for the domain.
    """

    domain: str
    pattern: str | None
    emails: list[HunterEmailRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HunterClient
# ---------------------------------------------------------------------------


class HunterClient:
    """Async HTTP client for the Hunter.io v2 REST API.

    Centralises authentication, rate-limiting, timeout, and error handling
    for all Hunter.io endpoints. The API key is never exposed in exceptions.

    Args:
        api_key: Hunter.io API key. Must be non-empty.
        http_client: Optional pre-built httpx.AsyncClient for DI / testing.
    """

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(10.0),
        )
        self._semaphore = asyncio.Semaphore(1)

    async def search_domain(self, domain: str) -> HunterDomainResult:
        """Fetch the email pattern and known addresses for a domain.

        Args:
            domain: The apex domain to query (e.g. ``"example.com"``).

        Returns:
            :class:`HunterDomainResult` with pattern and email list.

        Raises:
            HunterAPIError: Non-2xx response (key not included in message).
            HunterTimeoutError: Request timed out.
            HunterRateLimitError: HTTP 429 received.
        """
        data = await self._make_request("domain-search", {"domain": domain})
        return self._parse_domain_response(domain, data)

    async def find_email(
        self, domain: str, first_name: str, last_name: str
    ) -> tuple[str | None, int]:
        """Predict the most likely email address for a person at a domain.

        Args:
            domain: The apex domain.
            first_name: Subject's first name.
            last_name: Subject's last name.

        Returns:
            Tuple of (email address or None, confidence score 0–100).

        Raises:
            HunterAPIError: Non-2xx response.
            HunterTimeoutError: Request timed out.
            HunterRateLimitError: HTTP 429 received.
        """
        data = await self._make_request(
            "email-finder",
            {"domain": domain, "first_name": first_name, "last_name": last_name},
        )
        return self._parse_email_finder_response(data)

    async def close(self) -> None:
        """Close the underlying HTTP client if this instance owns it."""
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _make_request(
        self, endpoint: str, params: dict[str, str]
    ) -> dict[str, Any]:
        """Execute a GET request to a Hunter.io endpoint with rate limiting.

        Adds the API key to query parameters, enforces the inter-request
        interval (L009), and maps HTTP errors to typed exceptions (L007).

        Args:
            endpoint: Path segment after the base URL (e.g. ``"domain-search"``).
            params: Query parameters (API key is added internally).

        Returns:
            Parsed JSON response body as ``dict[str, Any]`` (L003).

        Raises:
            HunterRateLimitError: HTTP 429 response.
            HunterAPIError: Any other non-2xx response.
            HunterTimeoutError: Request exceeded timeout.
        """
        request_params = {**params, "api_key": self._api_key}
        url = f"{HUNTER_BASE}/{endpoint}"

        async with self._semaphore:
            try:
                response = await self._client.get(url, params=request_params)
                if response.status_code == 429:
                    retry_after = _parse_retry_after(response)
                    raise HunterRateLimitError(retry_after)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
            except HunterRateLimitError:
                raise
            except httpx.TimeoutException as exc:
                raise HunterTimeoutError(
                    f"Hunter.io request to {endpoint!r} timed out"
                ) from exc
            except httpx.HTTPStatusError as exc:
                # L007: re-raise WITHOUT exc to prevent URL (containing api_key)
                # from appearing in the exception chain.
                raise HunterAPIError(exc.response.status_code) from None
            finally:
                # L009: sleep runs even when the request raises.
                await asyncio.sleep(REQUEST_INTERVAL_SECONDS)

    def _parse_domain_response(
        self, domain: str, raw: dict[str, Any]
    ) -> HunterDomainResult:
        """Parse the domain-search JSON response into a HunterDomainResult.

        Args:
            domain: The queried domain (used as fallback if absent from response).
            raw: Parsed JSON body from the API.

        Returns:
            :class:`HunterDomainResult` with pattern and email list.
        """
        domain_data: dict[str, Any] = raw.get("data") or {}
        pattern: str | None = domain_data.get("pattern") or None
        raw_emails: list[Any] = domain_data.get("emails") or []

        emails: list[HunterEmailRecord] = []
        for entry in raw_emails:
            if not isinstance(entry, dict):
                continue
            value = entry.get("value", "")
            if not value:
                continue
            emails.append(
                HunterEmailRecord(
                    value=str(value),
                    email_type=str(entry.get("type") or "generic"),
                    confidence=int(entry.get("confidence") or 0),
                    first_name=entry.get("first_name") or None,
                    last_name=entry.get("last_name") or None,
                )
            )

        return HunterDomainResult(
            domain=str(domain_data.get("domain") or domain),
            pattern=pattern,
            emails=emails,
        )

    def _parse_email_finder_response(
        self, raw: dict[str, Any]
    ) -> tuple[str | None, int]:
        """Parse the email-finder JSON response.

        Args:
            raw: Parsed JSON body from the API.

        Returns:
            Tuple of (email address or None, confidence score).
        """
        email_data: dict[str, Any] = raw.get("data") or {}
        email: str | None = email_data.get("email") or None
        score = int(email_data.get("score") or 0)
        return email, score


# ---------------------------------------------------------------------------
# HunterModule
# ---------------------------------------------------------------------------


class HunterModule(BaseModule):
    """OSINT module that discovers email patterns via Hunter.io.

    Extracts the domain from ``inputs.email`` and optionally name parts from
    ``inputs.full_name``, then queries:
      - Hunter.io domain-search (always, if domain is available)
      - Hunter.io email-finder (only when first + last name are parseable)

    Produces up to three findings based on what is discovered.

    Args:
        client: Optional pre-built HunterClient for dependency injection.
    """

    def __init__(self, client: HunterClient | None = None) -> None:
        self._client = client or HunterClient(api_key=settings.hunter_api_key)

    @property
    def name(self) -> str:
        return "hunter"

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Run Hunter.io discovery for the scan subject.

        Returns failure immediately when the API key is absent or no email
        address is provided. Otherwise runs domain-search and, if name parts
        are available, email-finder.

        Args:
            inputs: Scan seed data. Uses ``email`` and ``full_name``.

        Returns:
            ModuleResult with email pattern and exposure findings.
        """
        if not settings.hunter_api_key:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["Hunter.io API key not configured"],
            )
        if not inputs.email:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["No email address provided for Hunter.io lookup"],
            )

        domain = _extract_domain_from_email(inputs.email)
        if not domain:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["Cannot extract domain from email address provided"],
            )

        domain_result, ds_errors = await self._run_domain_search(domain)
        name_parts = _parse_name_parts(inputs.full_name)
        predicted_email, confidence, ef_errors = await self._run_email_finder(
            domain, name_parts
        )

        all_errors = ds_errors + ef_errors
        findings = self._build_findings(
            domain, domain_result, predicted_email, confidence
        )
        return ModuleResult(
            module_name=self.name,
            success=bool(domain_result is not None or predicted_email is not None),
            findings=findings,
            errors=all_errors,
            metadata={
                "domain": domain,
                "pattern": domain_result.pattern if domain_result else None,
                "indexed_email_count": len(domain_result.emails)
                if domain_result
                else 0,
            },
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()

    # ------------------------------------------------------------------
    # Private async helpers
    # ------------------------------------------------------------------

    async def _run_domain_search(
        self, domain: str
    ) -> tuple[HunterDomainResult | None, list[str]]:
        """Run domain-search and return (result, errors) tuple.

        Args:
            domain: The domain to query.

        Returns:
            Tuple of (HunterDomainResult or None, list of error strings).
        """
        try:
            return await self._client.search_domain(domain), []
        except HunterError as exc:
            logger.warning("Hunter.io domain-search failed for %r: %s", domain, exc)
            return None, [f"domain-search: {exc}"]

    async def _run_email_finder(
        self,
        domain: str,
        name_parts: tuple[str, str] | None,
    ) -> tuple[str | None, int, list[str]]:
        """Run email-finder if name parts are available; skip otherwise.

        Args:
            domain: The domain to query.
            name_parts: (first_name, last_name) tuple, or None to skip.

        Returns:
            Tuple of (email or None, confidence int, list of error strings).
        """
        if not name_parts:
            return None, 0, []
        first, last = name_parts
        try:
            email, score = await self._client.find_email(domain, first, last)
            return email, score, []
        except HunterError as exc:
            logger.warning("Hunter.io email-finder failed for %r: %s", domain, exc)
            return None, 0, [f"email-finder: {exc}"]

    def _build_findings(
        self,
        domain: str,
        domain_result: HunterDomainResult | None,
        predicted_email: str | None,
        confidence: int,
    ) -> list[ModuleFinding]:
        """Assemble ModuleFinding objects from Hunter.io results.

        Args:
            domain: The queried domain (used in finding titles).
            domain_result: Parsed domain-search result, or None if it failed.
            predicted_email: Email predicted by email-finder, or None.
            confidence: Confidence score from email-finder (0 when not run).

        Returns:
            List of ModuleFinding objects (may be empty).
        """
        findings: list[ModuleFinding] = []

        if domain_result is not None and domain_result.pattern:
            findings.append(
                ModuleFinding(
                    finding_type="email_pattern_found",
                    severity=Severity.INFO,
                    category="domain",
                    title=(
                        f"Email pattern {domain_result.pattern!r} found for {domain}"
                    ),
                    description=(
                        f"The organization at {domain!r} uses a predictable email "
                        f"naming pattern ({domain_result.pattern}). Other email "
                        "addresses can be constructed from known names."
                    ),
                    platform="hunter.io",
                    evidence={
                        "domain": domain,
                        "pattern": domain_result.pattern,
                        "indexed_count": len(domain_result.emails),
                    },
                    remediation_action=(
                        "Consider whether your email address is guessable from "
                        "public profile data and use a non-patterned address where possible."
                    ),
                    remediation_effort="informational",
                    weight=0.3,
                )
            )

        if domain_result is not None and domain_result.emails:
            email_values = [r.value for r in domain_result.emails]
            findings.append(
                ModuleFinding(
                    finding_type="email_addresses_exposed",
                    severity=Severity.MEDIUM,
                    category="domain",
                    title=(
                        f"{len(domain_result.emails)} email address(es) for "
                        f"{domain} publicly indexed"
                    ),
                    description=(
                        f"Hunter.io has indexed {len(domain_result.emails)} email "
                        f"address(es) associated with {domain!r}. Public indexing of "
                        "organizational email addresses increases the phishing and "
                        "social engineering attack surface."
                    ),
                    platform="hunter.io",
                    evidence={
                        "domain": domain,
                        "email_count": len(domain_result.emails),
                        "emails": email_values,
                    },
                    remediation_action=(
                        "Review whether all indexed addresses should be public and "
                        "consider requesting removal from Hunter.io."
                    ),
                    remediation_effort="hard",
                    remediation_url="https://hunter.io/email-verifier",
                    weight=0.4,
                )
            )

        if predicted_email is not None and confidence >= EMAIL_CONFIDENCE_THRESHOLD:
            findings.append(
                ModuleFinding(
                    finding_type="email_address_confirmed",
                    severity=Severity.MEDIUM,
                    category="domain",
                    title=(
                        f"Email address {predicted_email} predicted with "
                        f"{confidence}% confidence"
                    ),
                    description=(
                        f"Hunter.io predicted {predicted_email!r} as the most likely "
                        f"email address for the subject with {confidence}% confidence. "
                        "High confidence indicates the address is likely deliverable."
                    ),
                    platform="hunter.io",
                    evidence={
                        "email": predicted_email,
                        "confidence": confidence,
                        "domain": domain,
                    },
                    remediation_action=(
                        "Verify whether this address is in active use and whether it "
                        "is appropriate to have it publicly discoverable."
                    ),
                    remediation_effort="informational",
                    weight=0.5,
                )
            )

        return findings


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_domain_from_email(email: str) -> str | None:
    """Extract the domain part from an email address.

    Args:
        email: An email address string.

    Returns:
        Lowercased domain part, or None if the address is malformed.
    """
    parts = email.strip().split("@")
    if len(parts) != 2 or not parts[1]:
        return None
    return parts[1].lower()


def _parse_name_parts(full_name: str | None) -> tuple[str, str] | None:
    """Split a full name into (first_name, last_name) for the email-finder.

    Only returns a tuple when the name contains exactly two whitespace-separated
    non-empty tokens. Single-word names (e.g. "Madonna") or names with more than
    two parts are not used — Hunter.io email-finder requires exactly first + last.

    Args:
        full_name: The subject's full name, or None.

    Returns:
        ``(first_name, last_name)`` tuple, or None if unparseable.
    """
    if not full_name:
        return None
    tokens = full_name.strip().split()
    if len(tokens) < 2:
        return None
    # Take first token as first name, last token as last name.
    # Middle names are ignored (Hunter.io only accepts first + last).
    return tokens[0], tokens[-1]


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Extract the Retry-After value from an HTTP 429 response header.

    Args:
        response: The httpx Response with status code 429.

    Returns:
        Seconds to wait as a float, or None if the header is absent/unparseable.
    """
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        return float(header)
    except ValueError:
        return None

"""Have I Been Pwned (HIBP) API v3 integration module.

Queries the HIBP API for email breach exposure data, classifies breach
severity based on exposed data classes, and checks password hashes
using the k-anonymity model (range endpoint).

HIBP rate-limits to 1 request per 1500ms per API key. We add a 100ms
buffer between requests to avoid edge-case 429 responses.

External docs: https://haveibeenpwned.com/API/v3
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field

import httpx

from piea.config import settings
from piea.core.cache import CacheLayer
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

HIBP_API_BASE = "https://haveibeenpwned.com/api/v3"
HIBP_PASSWORDS_BASE = "https://api.pwnedpasswords.com"
USER_AGENT = "PIEA-SecurityScanner/1.0"

# HIBP rate limit: 1 req / 1500ms + 100ms safety buffer
REQUEST_INTERVAL_SECONDS = 1.6

# Retry configuration for 429 responses
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 60.0

# Data classes that determine severity classification.
# These sets are used by classify_breach_severity() to map HIBP's
# "DataClasses" field to our severity tiers.
CRITICAL_DATA_CLASSES = frozenset({
    "Passwords",
    "Plaintext passwords",
    "Password hints",
    "Financial data",
    "Credit cards",
    "Bank account numbers",
    "Credit card CVV",
    "Credit status information",
    "Partial credit card data",
})

HIGH_DATA_CLASSES = frozenset({
    "Phone numbers",
    "Physical addresses",
    "Government issued IDs",
    "Passport numbers",
    "Social security numbers",
    "National IDs",
    "Tax IDs",
    "Driver's licenses",
    "Dates of birth",
})

MEDIUM_DATA_CLASSES = frozenset({
    "Email addresses",
    "Usernames",
    "IP addresses",
    "Device information",
    "Employers",
    "Job titles",
    "Geographic locations",
    "Genders",
    "Names",
    "Purchases",
})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HIBPError(Exception):
    """Base exception for HIBP module errors."""


class HIBPConfigError(HIBPError):
    """Raised when HIBP API key is not configured."""


# ---------------------------------------------------------------------------
# Breach data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BreachRecord:
    """A single breach record returned by the HIBP API.

    Attributes:
        name: Breach identifier (e.g. "Adobe").
        title: Human-readable breach name.
        domain: Domain of the breached service.
        breach_date: Date of the breach (ISO format string).
        added_date: When the breach was added to HIBP.
        pwn_count: Number of accounts affected.
        description: HTML description of the breach.
        data_classes: List of exposed data types.
        is_verified: Whether HIBP has verified the breach.
        is_sensitive: Whether the breach is considered sensitive.
        severity: Computed severity based on data classes.
    """

    name: str
    title: str
    domain: str
    breach_date: str
    added_date: str
    pwn_count: int
    description: str
    data_classes: list[str] = field(default_factory=list)
    is_verified: bool = False
    is_sensitive: bool = False
    severity: Severity = Severity.LOW


# ---------------------------------------------------------------------------
# Severity classifier
# ---------------------------------------------------------------------------


def classify_breach_severity(data_classes: list[str]) -> Severity:
    """Classify breach severity based on exposed data types.

    Classification rules (from SRS FR-2.1):
        Critical: Password hashes, plaintext passwords, or financial data
        High:     Phone numbers, physical addresses, or government IDs
        Medium:   Email addresses, usernames, or IP addresses
        Low:      Email-only exposure with no sensitive data classes

    Args:
        data_classes: List of data class names from the HIBP API response.

    Returns:
        The highest applicable severity level.
    """
    class_set = frozenset(data_classes)

    if class_set & CRITICAL_DATA_CLASSES:
        return Severity.CRITICAL
    if class_set & HIGH_DATA_CLASSES:
        return Severity.HIGH
    if class_set & MEDIUM_DATA_CLASSES:
        return Severity.MEDIUM
    return Severity.LOW


# ---------------------------------------------------------------------------
# HIBP Client
# ---------------------------------------------------------------------------


class HIBPClient:
    """Async client for the Have I Been Pwned API v3.

    Handles authentication, rate limiting, retries with exponential backoff,
    and response parsing. One instance should be shared across a scan.

    Args:
        api_key: HIBP API key. If empty, operations requiring auth will fail.
        http_client: Optional pre-configured httpx.AsyncClient. If not
            provided, one will be created (and must be closed via close()).
    """

    def __init__(
        self,
        api_key: str = "",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or settings.hibp_api_key
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "hibp-api-key": self._api_key,
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        # Semaphore enforces HIBP's rate limit: one request at a time
        # with a mandatory delay between requests.
        self._rate_semaphore = asyncio.Semaphore(1)

    async def fetch_breaches_for_email(self, email: str) -> list[BreachRecord]:
        """Query HIBP for all breaches associated with an email address.

        Args:
            email: The email address to check. Never logged in raw form.

        Returns:
            List of BreachRecord objects, each with severity classified.
            Returns an empty list if no breaches are found (HTTP 404).

        Raises:
            HIBPConfigError: If no API key is configured.
            RateLimitExceededError: If rate limit is hit after all retries.
            ModuleAPIError: If the API returns an unexpected error.
            ModuleTimeoutError: If the request times out.
        """
        if not self._api_key:
            raise HIBPConfigError(
                "HIBP API key is required. Set the HIBP_API_KEY environment variable."
            )

        email_hash = hashlib.sha256(email.encode()).hexdigest()[:8]
        logger.info("Fetching breaches for email hash %s...", email_hash)

        url = f"{HIBP_API_BASE}/breachedaccount/{email}"
        params = {"truncateResponse": "false"}

        response = await self._request_with_retry(url, params=params)

        if response.status_code == 404:
            logger.info("No breaches found for email hash %s", email_hash)
            return []

        response.raise_for_status()
        raw_breaches: list[dict[str, object]] = response.json()

        breaches = [self._parse_breach(raw) for raw in raw_breaches]
        logger.info(
            "Found %d breaches for email hash %s", len(breaches), email_hash
        )
        return breaches

    async def check_password_hash(self, sha1_prefix: str) -> dict[str, int]:
        """Check password exposure using the k-anonymity range endpoint.

        This endpoint does NOT require an API key and is not rate-limited
        the same way as the breach endpoint.

        Args:
            sha1_prefix: First 5 characters of the SHA-1 hash of the password.
                Must be exactly 5 hex characters. The full hash or password
                must NEVER be sent.

        Returns:
            Dict mapping hash suffixes to their occurrence counts.
            Example: {"1E4C9B93F3F0682250B6CF8331B7EE68FD8": 3861493}

        Raises:
            ValueError: If the prefix is not exactly 5 hex characters.
            ModuleAPIError: If the API returns an unexpected error.
            ModuleTimeoutError: If the request times out.
        """
        if len(sha1_prefix) != 5 or not all(c in "0123456789abcdefABCDEF" for c in sha1_prefix):
            raise ValueError("sha1_prefix must be exactly 5 hex characters")

        url = f"{HIBP_PASSWORDS_BASE}/range/{sha1_prefix}"
        # Password range endpoint uses a separate client without API key header
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(15.0, connect=10.0),
        ) as pw_client:
            try:
                response = await pw_client.get(url)
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise ModuleTimeoutError("hibp", "Password range request timed out") from exc
            except httpx.HTTPStatusError as exc:
                raise ModuleAPIError(
                    "hibp", exc.response.status_code, "Password range API error"
                ) from exc

        # Parse the response: each line is "SUFFIX:COUNT"
        suffix_counts: dict[str, int] = {}
        for line in response.text.strip().splitlines():
            suffix, count_str = line.split(":")
            suffix_counts[suffix] = int(count_str)

        return suffix_counts

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    async def _request_with_retry(
        self,
        url: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make an HTTP GET with rate-limiting, retries, and backoff.

        Args:
            url: The full URL to request.
            params: Optional query parameters.

        Returns:
            The HTTP response (caller must check status code).

        Raises:
            RateLimitExceededError: After exhausting all retries on 429.
            ModuleAPIError: On non-429 HTTP errors.
            ModuleTimeoutError: On request timeout.
        """
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(1, MAX_RETRIES + 1):
            async with self._rate_semaphore:
                try:
                    response = await self._client.get(url, params=params)
                except httpx.TimeoutException as exc:
                    raise ModuleTimeoutError(
                        "hibp", f"Request timed out (attempt {attempt}/{MAX_RETRIES})"
                    ) from exc

                # Enforce rate limit delay after every request
                await asyncio.sleep(REQUEST_INTERVAL_SECONDS)

            if response.status_code != 429:
                return response

            # Handle rate limiting with exponential backoff
            retry_after = float(
                response.headers.get("Retry-After", str(backoff))
            )
            logger.warning(
                "HIBP rate limited (attempt %d/%d), waiting %.1fs",
                attempt, MAX_RETRIES, retry_after,
            )
            await asyncio.sleep(retry_after)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)

        raise RateLimitExceededError("hibp", retry_after=backoff)

    @staticmethod
    def _parse_breach(raw: dict[str, object]) -> BreachRecord:
        """Parse a raw HIBP API breach response into a BreachRecord.

        Args:
            raw: A single breach dict from the HIBP JSON response.

        Returns:
            A fully populated BreachRecord with severity classified.
        """
        data_classes = list(raw.get("DataClasses", []))  # type: ignore[arg-type]
        severity = classify_breach_severity(data_classes)

        return BreachRecord(
            name=str(raw.get("Name", "")),
            title=str(raw.get("Title", "")),
            domain=str(raw.get("Domain", "")),
            breach_date=str(raw.get("BreachDate", "")),
            added_date=str(raw.get("AddedDate", "")),
            pwn_count=int(raw.get("PwnCount", 0)),  # type: ignore[arg-type]
            description=str(raw.get("Description", "")),
            data_classes=data_classes,
            is_verified=bool(raw.get("IsVerified", False)),
            is_sensitive=bool(raw.get("IsSensitive", False)),
            severity=severity,
        )


# ---------------------------------------------------------------------------
# HIBP Module (BaseModule implementation)
# ---------------------------------------------------------------------------


class HIBPModule(BaseModule):
    """OSINT module that checks email breach exposure via HIBP.

    Wraps HIBPClient and translates BreachRecords into the standard
    ModuleFinding/ModuleResult format expected by the scan orchestrator.

    Caching: Breach results are cached in Redis keyed by SHA-256 hash
    of the email address, with a TTL of cache_ttl_breach seconds (default 24h).
    """

    def __init__(
        self,
        client: HIBPClient | None = None,
        cache: CacheLayer | None = None,
    ) -> None:
        self._client = client or HIBPClient()
        self._cache = cache

    @property
    def name(self) -> str:
        return "hibp"

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Execute breach lookup for the provided email.

        Returns a ModuleResult with success=False (not an exception) if
        the email is missing or the API fails. This follows the graceful
        degradation requirement (NFR-R1): individual module failure must
        not crash the entire scan.
        """
        if not inputs.email:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["No email address provided for breach lookup"],
            )

        cache_key = hashlib.sha256(inputs.email.encode()).hexdigest()

        # Try cache first
        cached_result = await self._get_cached(cache_key)
        if cached_result is not None:
            email_hash = cache_key[:8]
            logger.info("Cache hit for email hash %s", email_hash)
            findings = [self._breach_to_finding(b) for b in cached_result]
            return ModuleResult(
                module_name=self.name,
                success=True,
                findings=findings,
                cached=True,
                metadata={
                    "total_breaches": len(cached_result),
                    "verified_breaches": sum(1 for b in cached_result if b.is_verified),
                },
            )

        # Cache miss — fetch from API
        try:
            breaches = await self._client.fetch_breaches_for_email(inputs.email)
        except HIBPConfigError as exc:
            logger.error("HIBP module skipped: %s", exc)
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=[str(exc)],
            )
        except (ModuleAPIError, ModuleTimeoutError, RateLimitExceededError) as exc:
            logger.error("HIBP module failed: %s", exc)
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=[str(exc)],
            )

        # Cache the result
        await self._set_cached(cache_key, breaches)

        findings = [self._breach_to_finding(breach) for breach in breaches]

        return ModuleResult(
            module_name=self.name,
            success=True,
            findings=findings,
            metadata={
                "total_breaches": len(breaches),
                "verified_breaches": sum(1 for b in breaches if b.is_verified),
            },
        )

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        await self._client.close()

    # -------------------------------------------------------------------
    # Cache helpers
    # -------------------------------------------------------------------

    async def _get_cached(self, cache_key: str) -> list[BreachRecord] | None:
        """Attempt to retrieve breach records from cache."""
        if self._cache is None:
            return None
        raw = await self._cache.get("breach", cache_key)
        if raw is None or not isinstance(raw, list):
            return None
        try:
            return [
                BreachRecord(
                    name=item["name"],
                    title=item["title"],
                    domain=item["domain"],
                    breach_date=item["breach_date"],
                    added_date=item["added_date"],
                    pwn_count=item["pwn_count"],
                    description=item["description"],
                    data_classes=item["data_classes"],
                    is_verified=item["is_verified"],
                    is_sensitive=item["is_sensitive"],
                    severity=Severity(item["severity"]),
                )
                for item in raw
            ]
        except (KeyError, ValueError, TypeError):
            logger.warning("Corrupt cache entry for key %s, ignoring", cache_key[:8])
            return None

    async def _set_cached(self, cache_key: str, breaches: list[BreachRecord]) -> None:
        """Store breach records in cache."""
        if self._cache is None:
            return
        serializable = [
            {
                "name": b.name,
                "title": b.title,
                "domain": b.domain,
                "breach_date": b.breach_date,
                "added_date": b.added_date,
                "pwn_count": b.pwn_count,
                "description": b.description,
                "data_classes": b.data_classes,
                "is_verified": b.is_verified,
                "is_sensitive": b.is_sensitive,
                "severity": b.severity.value,
            }
            for b in breaches
        ]
        await self._cache.set(
            "breach", cache_key, serializable, ttl_seconds=settings.cache_ttl_breach
        )

    @staticmethod
    def _breach_to_finding(breach: BreachRecord) -> ModuleFinding:
        """Convert a BreachRecord into a standard ModuleFinding."""
        # Build a human-readable description
        exposed = ", ".join(breach.data_classes[:5])
        if len(breach.data_classes) > 5:
            exposed += f" (+{len(breach.data_classes) - 5} more)"

        description = (
            f"Your email was exposed in the {breach.title} breach "
            f"({breach.breach_date}). "
            f"Exposed data: {exposed}. "
            f"This breach affected {breach.pwn_count:,} accounts."
        )

        # Weight is higher for verified, more severe breaches
        weight = _severity_weight(breach.severity)
        if breach.is_verified:
            weight = min(weight + 0.1, 1.0)

        return ModuleFinding(
            finding_type="breach_exposure",
            severity=breach.severity,
            category="breach",
            title=f"Email exposed in {breach.title} breach ({breach.severity.value})",
            description=description,
            platform=breach.domain or breach.name,
            evidence={
                "breach_name": breach.name,
                "breach_date": breach.breach_date,
                "data_classes": breach.data_classes,
                "pwn_count": breach.pwn_count,
                "is_verified": breach.is_verified,
            },
            remediation_action=_remediation_for_severity(breach.severity),
            remediation_effort=_effort_for_severity(breach.severity),
            weight=weight,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _severity_weight(severity: Severity) -> float:
    """Map severity to a base scoring weight."""
    return {
        Severity.CRITICAL: 0.9,
        Severity.HIGH: 0.7,
        Severity.MEDIUM: 0.5,
        Severity.LOW: 0.3,
        Severity.INFO: 0.1,
    }[severity]


def _remediation_for_severity(severity: Severity) -> str:
    """Return remediation advice based on breach severity."""
    if severity == Severity.CRITICAL:
        return (
            "Immediately change your password on this service and any other "
            "service where you used the same password. Enable two-factor "
            "authentication wherever possible."
        )
    if severity == Severity.HIGH:
        return (
            "Change your password on this service. Review your account for "
            "unauthorized access. Consider enabling two-factor authentication."
        )
    if severity == Severity.MEDIUM:
        return (
            "Change your password if you haven't already. Be alert for "
            "phishing attempts using the exposed information."
        )
    return (
        "No immediate action required, but consider changing your password "
        "and monitoring for suspicious activity."
    )


def _effort_for_severity(severity: Severity) -> str:
    """Return estimated remediation effort based on severity."""
    if severity in (Severity.CRITICAL, Severity.HIGH):
        return "moderate"
    return "easy"

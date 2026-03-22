"""HIBP paste-account exposure module (T3.7).

Queries the Have I Been Pwned (HIBP) paste-account endpoint:
  https://haveibeenpwned.com/api/v3/pasteaccount/{email}

For each paste found, a HIGH-severity finding is emitted with source, title,
paste identifier, date, and email count.

The request URL contains the subject's email address as a path component.
httpx.HTTPStatusError is caught and re-raised WITHOUT the URL to prevent PII
leakage in the exception chain (L007/L016 pattern).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
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

HIBP_PASTE_BASE = "https://haveibeenpwned.com/api/v3/pasteaccount"
USER_AGENT = "PIEA-SecurityScanner/1.0"

# HIBP enforces a 1500ms minimum; use 1.6s to match the existing hibp.py buffer.
REQUEST_INTERVAL_SECONDS: float = 1.6


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PasteMonitorError(Exception):
    """Base exception for PasteMonitor module errors."""


class PasteMonitorAPIError(PasteMonitorError):
    """Raised when the HIBP paste-account API returns an unexpected HTTP error.

    The original httpx.HTTPStatusError is NOT chained to prevent email PII
    leakage via the request URL (L007 — URL contains email as path segment).

    Attributes:
        status_code: HTTP status code returned by the API.
    """

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HIBP paste API returned HTTP {status_code}")


class PasteMonitorTimeoutError(PasteMonitorError):
    """Raised when a HIBP paste-account request exceeds its timeout."""


class PasteMonitorRateLimitError(PasteMonitorError):
    """Raised when HIBP returns HTTP 429 (rate limit exceeded).

    Attributes:
        retry_after: Seconds to wait before retrying, or None if not provided.
    """

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "HIBP paste API rate limit exceeded"
        if retry_after is not None:
            msg += f" (retry after {retry_after:.0f}s)"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PasteRecord:
    """A single paste record returned by the HIBP paste-account endpoint.

    Attributes:
        source: Paste site name (e.g. ``"Pastebin"``, ``"Ghostbin"``).
        title: Paste title, or None if absent.
        paste_id: Site-specific paste identifier, or None.
        paste_date: ISO 8601 date string, or None.
        email_count: Number of email addresses in the paste.
    """

    source: str
    title: str | None
    paste_id: str | None
    paste_date: str | None
    email_count: int


# ---------------------------------------------------------------------------
# PasteClient
# ---------------------------------------------------------------------------


class PasteClient:
    """Async HTTP client for the HIBP paste-account REST endpoint.

    Centralises authentication, rate-limiting, timeout, and error handling.
    The email address is never exposed in exceptions (L007/L016).

    Args:
        api_key: HIBP API key. Must be non-empty.
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

    async def get_paste_exposure(self, email: str) -> list[PasteRecord]:
        """Fetch the list of pastes in which the email address appears.

        Args:
            email: The email address to query.

        Returns:
            List of :class:`PasteRecord` objects (empty when no pastes found).

        Raises:
            PasteMonitorAPIError: Non-2xx, non-404 response (PII not in chain).
            PasteMonitorTimeoutError: Request timed out.
            PasteMonitorRateLimitError: HTTP 429 received.
        """
        raw = await self._make_request(email)
        return self._parse_response(raw)

    async def close(self) -> None:
        """Close the underlying HTTP client if this instance owns it."""
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _make_request(self, email: str) -> list[dict[str, Any]]:
        """Execute a GET request to the HIBP paste-account endpoint.

        Enforces the inter-request interval (L009) and maps HTTP errors to
        typed exceptions without exposing the email in the chain (L007/L016).

        Args:
            email: Email address used as the URL path segment.

        Returns:
            Parsed JSON response body as a list of raw dicts (L003).
            Returns an empty list when HIBP returns HTTP 404 (no pastes).

        Raises:
            PasteMonitorRateLimitError: HTTP 429 response.
            PasteMonitorAPIError: Any other non-2xx response.
            PasteMonitorTimeoutError: Request exceeded timeout.
        """
        url = f"{HIBP_PASTE_BASE}/{email}"

        async with self._semaphore:
            try:
                response = await self._client.get(
                    url,
                    headers={"hibp-api-key": self._api_key},
                )
                if response.status_code == 404:
                    # Clean result — no pastes found for this email address.
                    return []
                if response.status_code == 429:
                    raise PasteMonitorRateLimitError(_parse_retry_after(response))
                response.raise_for_status()
                result: list[dict[str, Any]] = response.json()
                return result
            except PasteMonitorRateLimitError:
                raise
            except httpx.TimeoutException as exc:
                raise PasteMonitorTimeoutError(
                    "HIBP paste-account request timed out"
                ) from exc
            except httpx.HTTPStatusError as exc:
                # L007/L016: re-raise WITHOUT exc to prevent URL (containing
                # the email address as a path segment) from appearing in the
                # exception chain and leaking PII into logs.
                raise PasteMonitorAPIError(exc.response.status_code) from None
            finally:
                # L009: sleep runs even when the request raises.
                await asyncio.sleep(REQUEST_INTERVAL_SECONDS)

    def _parse_response(self, raw: list[dict[str, Any]]) -> list[PasteRecord]:
        """Parse the HIBP paste-account JSON response into PasteRecord objects.

        Args:
            raw: List of raw paste dicts from the API.

        Returns:
            List of :class:`PasteRecord` objects.
        """
        records: list[PasteRecord] = []
        for entry in raw:
            source = str(entry.get("Source") or "Unknown")
            records.append(
                PasteRecord(
                    source=source,
                    title=entry.get("Title") or None,
                    paste_id=entry.get("Id") or None,
                    paste_date=entry.get("Date") or None,
                    email_count=int(entry.get("EmailCount") or 0),
                )
            )
        return records


# ---------------------------------------------------------------------------
# PasteMonitor
# ---------------------------------------------------------------------------


class PasteMonitor(BaseModule):
    """OSINT module that checks for email exposure on paste sites via HIBP.

    Queries the HIBP paste-account endpoint for the subject's email address.
    Emits one HIGH-severity finding per paste in which the address appears.

    Args:
        client: Optional pre-built PasteClient for dependency injection.
    """

    def __init__(self, client: PasteClient | None = None) -> None:
        self._client = client or PasteClient(api_key=settings.hibp_api_key)

    @property
    def name(self) -> str:
        return "paste_monitor"

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Run paste-site exposure check for the scan subject.

        Returns failure immediately when the API key is absent or no email
        address is provided. A clean HIBP result (404 / no pastes) is returned
        as ``success=True`` with an empty findings list.

        Args:
            inputs: Scan seed data. Uses ``email`` only.

        Returns:
            ModuleResult with paste exposure findings.
        """
        if not settings.hibp_api_key:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["HIBP API key not configured"],
            )
        if not inputs.email:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["No email address provided for paste site check"],
            )

        pastes, errors = await self._run_paste_check(inputs.email)
        findings = self._build_findings(pastes)
        return ModuleResult(
            module_name=self.name,
            success=len(errors) == 0,
            findings=findings,
            errors=errors,
            metadata={"paste_count": len(pastes)},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_paste_check(self, email: str) -> tuple[list[PasteRecord], list[str]]:
        """Call the paste client and convert exceptions to error strings.

        Args:
            email: Email address to look up.

        Returns:
            Tuple of (paste records, list of error strings).
        """
        try:
            pastes = await self._client.get_paste_exposure(email)
            return pastes, []
        except PasteMonitorError as exc:
            logger.warning("HIBP paste check failed: %s", exc)
            return [], [str(exc)]

    def _build_findings(self, pastes: list[PasteRecord]) -> list[ModuleFinding]:
        """Assemble ModuleFinding objects from paste records.

        Emits one HIGH-severity finding per paste (FR-7.1).

        Args:
            pastes: List of paste records returned by the HIBP API.

        Returns:
            List of ModuleFinding objects (empty when no pastes found).
        """
        findings: list[ModuleFinding] = []
        for paste in pastes:
            title = paste.title or f"Untitled paste on {paste.source}"
            findings.append(
                ModuleFinding(
                    finding_type="paste_exposure",
                    severity=Severity.HIGH,
                    category="credential_exposure",
                    title=f"Email address found in paste on {paste.source}: {title}",
                    description=(
                        f"The subject's email address appears in a paste titled "
                        f"{title!r} on {paste.source}. "
                        f"The paste contains {paste.email_count} email address(es). "
                        "Paste site exposure often indicates credential leakage from "
                        "a data breach or targeted dump."
                    ),
                    platform=paste.source,
                    evidence={
                        "source": paste.source,
                        "title": paste.title,
                        "paste_id": paste.paste_id,
                        "paste_date": paste.paste_date,
                        "email_count": paste.email_count,
                    },
                    remediation_action=(
                        "Change any passwords associated with this email address "
                        "and enable multi-factor authentication."
                    ),
                    remediation_effort="hard",
                    remediation_url="https://haveibeenpwned.com/",
                    weight=0.7,
                )
            )
        return findings


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


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

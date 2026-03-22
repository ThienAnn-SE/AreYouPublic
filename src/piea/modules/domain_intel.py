"""Domain intelligence module: WHOIS registration lookup and DNS security posture.

Extracts the domain from the scan subject's email address and runs two
independent analyses:
  - FR-6.1: WHOIS registration data (privacy protection, registrant exposure)
  - FR-6.2: DNS email security posture (MX, SPF, DMARC) with 4-tier classification

Both WHOIS (python-whois) and DNS (dnspython resolver) are blocking libraries;
all network calls are wrapped in asyncio.to_thread() to avoid blocking the
event loop.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import dns.exception
import dns.resolver
import whois  # type: ignore[import-untyped]

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

WHOIS_TIMEOUT_SECONDS: int = 10

# Substrings that indicate a WHOIS privacy/proxy service is masking real data.
# Case-insensitive comparison is applied at lookup time.
_PRIVACY_KEYWORDS: frozenset[str] = frozenset(
    {
        "privacy",
        "protect",
        "proxy",
        "whoisguard",
        "redacted",
        "contact privacy",
        "withheld",
        "not disclosed",
        "data protected",
    }
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DomainIntelError(Exception):
    """Base exception for domain intelligence module errors."""


class DomainIntelTimeoutError(DomainIntelError):
    """Raised when a WHOIS or DNS query exceeds its timeout."""


class DomainIntelLookupError(DomainIntelError):
    """Raised when a domain is not found or returns no data."""


class DomainIntelRateLimitError(DomainIntelError):
    """Raised when a WHOIS server rate-limits the request."""


# ---------------------------------------------------------------------------
# WHOIS data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WhoisData:
    """Parsed WHOIS registration data for a domain.

    Attributes:
        domain: The queried domain name.
        registrant_name: Registrant's full name, or None if hidden/absent.
        registrant_org: Registrant's organization, or None if hidden/absent.
        registration_date: Domain registration date, or None if unavailable.
        expiration_date: Domain expiration date, or None if unavailable.
        registrar: Registrar name, or None if unavailable.
        name_servers: List of authoritative name server hostnames.
        privacy_protected: True if a privacy/proxy service masks real data.
    """

    domain: str
    registrant_name: str | None
    registrant_org: str | None
    registration_date: datetime | None
    expiration_date: datetime | None
    registrar: str | None
    name_servers: list[str] = field(default_factory=list)
    privacy_protected: bool = False


# ---------------------------------------------------------------------------
# DNS security data structures
# ---------------------------------------------------------------------------


class EmailSecurityTier(StrEnum):
    """Email security classification based on SPF and DMARC posture."""

    STRONG = "strong"  # SPF + DMARC p=reject or p=quarantine
    MODERATE = "moderate"  # SPF + DMARC p=none
    WEAK = "weak"  # SPF present, no DMARC
    NONE = "none"  # No SPF (and no DMARC)


@dataclass(frozen=True, slots=True)
class DnsSecurityPosture:
    """DNS email security posture for a domain.

    Attributes:
        domain: The analyzed domain name.
        has_mx: True if at least one MX record exists.
        spf_record: Raw TXT value of the SPF record, or None if absent.
        dmarc_record: Raw TXT value of the DMARC record, or None if absent.
        dmarc_policy: Extracted ``p=`` value from the DMARC record, or None.
        email_security_tier: Four-tier classification of email security strength.
    """

    domain: str
    has_mx: bool
    spf_record: str | None
    dmarc_record: str | None
    dmarc_policy: str | None
    email_security_tier: EmailSecurityTier


# ---------------------------------------------------------------------------
# WhoisClient
# ---------------------------------------------------------------------------


class WhoisClient:
    """Async wrapper around the blocking python-whois library.

    Wraps ``whois.whois()`` in ``asyncio.to_thread()`` to avoid blocking the
    event loop. Maps all library-level exceptions to typed ``DomainIntelError``
    subclasses so callers never need to inspect raw third-party exception types.
    """

    async def lookup(self, domain: str) -> WhoisData:
        """Perform a WHOIS lookup for the given domain.

        Args:
            domain: The apex domain to query (e.g. ``"example.com"``).

        Returns:
            :class:`WhoisData` with parsed registration fields.

        Raises:
            DomainIntelTimeoutError: The WHOIS server did not respond in time.
            DomainIntelLookupError: The domain was not found or returned no data.
            DomainIntelRateLimitError: The WHOIS server rate-limited the request.
            DomainIntelError: Any other WHOIS lookup failure.
        """
        try:
            raw: Any = await asyncio.to_thread(whois.whois, domain)
        except TimeoutError as exc:
            raise DomainIntelTimeoutError(
                f"WHOIS lookup timed out for {domain!r}"
            ) from exc
        except Exception as exc:
            self._remap_exception(domain, exc)
        return self._parse(domain, raw)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _remap_exception(self, domain: str, exc: Exception) -> None:
        """Re-raise exc as an appropriate DomainIntelError subclass.

        Inspects the exception type name and message to classify it.
        Never returns normally — always raises.

        Args:
            domain: The domain being queried (used in the error message).
            exc: The original exception from python-whois.

        Raises:
            DomainIntelTimeoutError: Timeout-like exception detected.
            DomainIntelRateLimitError: Rate-limiting message detected.
            DomainIntelLookupError: Not-found or no-data condition.
            DomainIntelError: All other failures.
        """
        msg = str(exc).lower()
        type_name = type(exc).__name__.lower()
        if "timeout" in msg or "timeout" in type_name:
            raise DomainIntelTimeoutError(
                f"WHOIS lookup timed out for {domain!r}"
            ) from exc
        if "rate" in msg or "limit" in msg:
            raise DomainIntelRateLimitError(
                f"WHOIS rate limited for {domain!r}"
            ) from exc
        if (
            "no match" in msg
            or "not found" in msg
            or "no data" in msg
            or "nodataexception" in type_name
        ):
            raise DomainIntelLookupError(
                f"WHOIS returned no data for {domain!r}"
            ) from exc
        raise DomainIntelError(f"WHOIS lookup failed for {domain!r}") from exc

    def _parse(self, domain: str, raw: Any) -> WhoisData:
        """Convert the raw python-whois response object to WhoisData.

        Args:
            domain: The queried domain name.
            raw: The dict-like WhoisEntry returned by python-whois.

        Returns:
            Populated :class:`WhoisData` instance.
        """
        # python-whois returns None for the whole response if domain not found
        if raw is None:
            raise DomainIntelLookupError(f"WHOIS returned no data for {domain!r}")

        registrant_name = _coerce_first(raw.get("name"))
        registrant_org = _coerce_first(raw.get("org"))
        registrar = _coerce_first(raw.get("registrar"))
        name_servers = _coerce_list(raw.get("name_servers"))
        registration_date = _coerce_date(raw.get("creation_date"))
        expiration_date = _coerce_date(raw.get("expiration_date"))

        privacy_protected = _detect_privacy(registrant_name, registrant_org)

        return WhoisData(
            domain=domain,
            registrant_name=registrant_name,
            registrant_org=registrant_org,
            registration_date=registration_date,
            expiration_date=expiration_date,
            registrar=registrar,
            name_servers=name_servers,
            privacy_protected=privacy_protected,
        )


# ---------------------------------------------------------------------------
# DNSAnalyzer
# ---------------------------------------------------------------------------


class DNSAnalyzer:
    """Analyzes DNS records to determine a domain's email security posture.

    Queries MX, SPF (TXT), and DMARC (TXT at ``_dmarc.{domain}``) records
    using ``dnspython``. All queries are wrapped in ``asyncio.to_thread()``
    to avoid blocking the event loop.
    """

    async def analyze(self, domain: str) -> DnsSecurityPosture:
        """Analyze the DNS email security posture for a domain.

        Queries MX records, TXT records for SPF, and TXT records at the DMARC
        subdomain. Classifies the result into one of four security tiers.

        Args:
            domain: The apex domain to analyze (e.g. ``"example.com"``).

        Returns:
            :class:`DnsSecurityPosture` with all parsed DNS findings.

        Raises:
            DomainIntelTimeoutError: A DNS query timed out.
            DomainIntelLookupError: The domain does not exist (NXDOMAIN).
            DomainIntelError: Any other DNS failure.
        """
        try:
            has_mx = await asyncio.to_thread(self._query_has_mx, domain)
            txt_records = await asyncio.to_thread(self._query_txt_records, domain)
            dmarc_records = await asyncio.to_thread(
                self._query_txt_records, f"_dmarc.{domain}"
            )
        except dns.exception.Timeout as exc:
            raise DomainIntelTimeoutError(
                f"DNS query timed out for {domain!r}"
            ) from exc
        except dns.resolver.NXDOMAIN as exc:
            raise DomainIntelLookupError(
                f"Domain {domain!r} does not exist (NXDOMAIN)"
            ) from exc
        except (dns.resolver.NoNameservers, dns.resolver.NoAnswer):
            # Domain exists but has no records of the queried type — not an error.
            txt_records = []
            dmarc_records = []
            has_mx = False
        except Exception as exc:
            raise DomainIntelError(f"DNS lookup failed for {domain!r}") from exc

        spf_record = self._find_spf(txt_records)
        dmarc_record = self._find_dmarc(dmarc_records)
        tier, dmarc_policy = self._classify_tier(spf_record, dmarc_record)

        return DnsSecurityPosture(
            domain=domain,
            has_mx=has_mx,
            spf_record=spf_record,
            dmarc_record=dmarc_record,
            dmarc_policy=dmarc_policy,
            email_security_tier=tier,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query_has_mx(self, domain: str) -> bool:
        """Return True if the domain has at least one MX record.

        Intended to be run via asyncio.to_thread().

        Args:
            domain: The domain to query.

        Returns:
            True if any MX records are present.
        """
        try:
            answers = dns.resolver.resolve(domain, "MX")
            return len(answers) > 0
        except (
            dns.resolver.NoAnswer,
            dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers,
        ):
            return False

    def _query_txt_records(self, domain: str) -> list[str]:
        """Retrieve all TXT record strings for a domain.

        Intended to be run via asyncio.to_thread(). Returns an empty list
        for NXDOMAIN and NoAnswer (the _dmarc subdomain commonly doesn't exist).

        Args:
            domain: The domain or subdomain to query TXT records for.

        Returns:
            List of decoded TXT record strings.
        """
        try:
            answers = dns.resolver.resolve(domain, "TXT")
            records: list[str] = []
            for rdata in answers:
                # Each rdata.strings is a list of bytes; join and decode.
                text = b"".join(rdata.strings).decode("utf-8", errors="replace")
                records.append(text)
            return records
        except (
            dns.resolver.NoAnswer,
            dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers,
        ):
            return []

    def _find_spf(self, txt_records: list[str]) -> str | None:
        """Return the first SPF record found among TXT records, or None.

        Args:
            txt_records: All TXT record strings for the domain.

        Returns:
            The raw SPF record string, or None if not present.
        """
        for record in txt_records:
            if record.strip().lower().startswith("v=spf1"):
                return record
        return None

    def _find_dmarc(self, dmarc_txt_records: list[str]) -> str | None:
        """Return the first DMARC record found, or None.

        Args:
            dmarc_txt_records: TXT records from ``_dmarc.{domain}``.

        Returns:
            The raw DMARC record string, or None if not present.
        """
        for record in dmarc_txt_records:
            if record.strip().upper().startswith("V=DMARC1"):
                return record
        return None

    def _extract_dmarc_policy(self, dmarc_record: str) -> str | None:
        """Extract the ``p=`` policy value from a DMARC TXT record.

        Args:
            dmarc_record: Raw DMARC record string (e.g. ``"v=DMARC1; p=reject"``).

        Returns:
            Lowercased policy value (e.g. ``"reject"``), or None if absent.
        """
        match = re.search(r"p=(\w+)", dmarc_record, re.IGNORECASE)
        return match.group(1).lower() if match else None

    def _classify_tier(
        self,
        spf_record: str | None,
        dmarc_record: str | None,
    ) -> tuple[EmailSecurityTier, str | None]:
        """Classify email security tier from SPF and DMARC presence/policy.

        Args:
            spf_record: Raw SPF record string, or None.
            dmarc_record: Raw DMARC record string, or None.

        Returns:
            Tuple of (EmailSecurityTier, dmarc_policy_str_or_None).
        """
        dmarc_policy: str | None = None
        if dmarc_record:
            dmarc_policy = self._extract_dmarc_policy(dmarc_record)

        if spf_record and dmarc_record and dmarc_policy in {"reject", "quarantine"}:
            return EmailSecurityTier.STRONG, dmarc_policy
        if spf_record and dmarc_record and dmarc_policy == "none":
            return EmailSecurityTier.MODERATE, dmarc_policy
        if spf_record and not dmarc_record:
            return EmailSecurityTier.WEAK, None
        return EmailSecurityTier.NONE, dmarc_policy


# ---------------------------------------------------------------------------
# DomainIntelModule
# ---------------------------------------------------------------------------


class DomainIntelModule(BaseModule):
    """OSINT module that analyzes WHOIS and DNS records for a subject's email domain.

    Extracts the domain from ``inputs.email``, then runs WHOIS (FR-6.1) and
    DNS email-security checks (FR-6.2) concurrently via asyncio.gather(). Both
    analyses are independent and failure of one does not prevent the other.

    Args:
        whois_client: Optional pre-built WhoisClient for dependency injection.
        dns_analyzer: Optional pre-built DNSAnalyzer for dependency injection.
    """

    def __init__(
        self,
        whois_client: WhoisClient | None = None,
        dns_analyzer: DNSAnalyzer | None = None,
    ) -> None:
        self._whois = whois_client or WhoisClient()
        self._dns = dns_analyzer or DNSAnalyzer()

    @property
    def name(self) -> str:
        return "domain_intel"

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Run WHOIS and DNS analysis against the domain extracted from inputs.email.

        Returns a partial success result if only one analysis fails. Returns
        success=False only when both analyses fail or no domain can be extracted.

        Args:
            inputs: Scan seed data. Only ``email`` is used.

        Returns:
            ModuleResult with WHOIS privacy and DNS security findings.
        """
        if not inputs.email:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["No email address provided; cannot extract domain"],
            )
        domain = self._extract_domain(inputs.email)
        if not domain:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["Cannot extract domain from email address provided"],
            )

        whois_data, whois_errors = await self._run_whois(domain)
        posture, dns_errors = await self._run_dns(domain)
        all_errors = whois_errors + dns_errors
        findings = self._build_findings(whois_data, posture)

        tier_value = posture.email_security_tier.value if posture else None
        return ModuleResult(
            module_name=self.name,
            success=bool(whois_data or posture),
            findings=findings,
            errors=all_errors,
            metadata={
                "domain": domain,
                "email_security_tier": tier_value,
            },
        )

    @staticmethod
    def _extract_domain(email: str) -> str | None:
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

    # ------------------------------------------------------------------
    # Private async helpers
    # ------------------------------------------------------------------

    async def _run_whois(self, domain: str) -> tuple[WhoisData | None, list[str]]:
        """Run WHOIS lookup, returning (data, errors) tuple.

        Catches all DomainIntelError subclasses and converts them to error
        strings so the caller never needs to handle them explicitly.

        Args:
            domain: The domain to query.

        Returns:
            Tuple of (WhoisData or None, list of error strings).
        """
        try:
            return await self._whois.lookup(domain), []
        except DomainIntelError as exc:
            logger.warning("WHOIS lookup failed for %r: %s", domain, exc)
            return None, [f"WHOIS: {exc}"]

    async def _run_dns(
        self, domain: str
    ) -> tuple[DnsSecurityPosture | None, list[str]]:
        """Run DNS analysis, returning (posture, errors) tuple.

        Args:
            domain: The domain to analyze.

        Returns:
            Tuple of (DnsSecurityPosture or None, list of error strings).
        """
        try:
            return await self._dns.analyze(domain), []
        except DomainIntelError as exc:
            logger.warning("DNS analysis failed for %r: %s", domain, exc)
            return None, [f"DNS: {exc}"]

    # ------------------------------------------------------------------
    # Finding builders
    # ------------------------------------------------------------------

    def _build_findings(
        self,
        whois_data: WhoisData | None,
        posture: DnsSecurityPosture | None,
    ) -> list[ModuleFinding]:
        """Assemble all ModuleFinding objects from analysis results.

        Args:
            whois_data: Parsed WHOIS data, or None if lookup failed.
            posture: DNS security posture, or None if DNS analysis failed.

        Returns:
            List of ModuleFinding objects (may be empty).
        """
        findings: list[ModuleFinding] = []
        if whois_data is not None:
            finding = self._build_whois_finding(whois_data)
            if finding:
                findings.append(finding)
        if posture is not None:
            spf_finding = self._build_spf_finding(posture)
            if spf_finding:
                findings.append(spf_finding)
            dmarc_finding = self._build_dmarc_finding(posture)
            if dmarc_finding:
                findings.append(dmarc_finding)
        return findings

    def _build_whois_finding(self, whois_data: WhoisData) -> ModuleFinding | None:
        """Return a HIGH finding when WHOIS data is unprotected and personal.

        No finding is produced when privacy protection is enabled or when no
        personal information is actually visible.

        Args:
            whois_data: The parsed WHOIS registration data.

        Returns:
            ModuleFinding or None.
        """
        if whois_data.privacy_protected:
            return None
        if not whois_data.registrant_name and not whois_data.registrant_org:
            return None

        visible = ", ".join(
            v for v in [whois_data.registrant_name, whois_data.registrant_org] if v
        )
        return ModuleFinding(
            finding_type="whois_privacy_missing",
            severity=Severity.HIGH,
            category="domain",
            title=f"WHOIS registration data is publicly visible for {whois_data.domain}",
            description=(
                f"The domain {whois_data.domain!r} has no WHOIS privacy protection "
                f"enabled. Registrant information ({visible}) is publicly accessible, "
                "exposing personal contact data to anyone who performs a WHOIS lookup."
            ),
            platform="whois",
            evidence={
                "domain": whois_data.domain,
                "registrant_name": whois_data.registrant_name,
                "registrant_org": whois_data.registrant_org,
                "registrar": whois_data.registrar,
                "registration_date": (
                    whois_data.registration_date.isoformat()
                    if whois_data.registration_date
                    else None
                ),
                "expiration_date": (
                    whois_data.expiration_date.isoformat()
                    if whois_data.expiration_date
                    else None
                ),
            },
            remediation_action=(
                "Enable WHOIS privacy protection through your domain registrar."
            ),
            remediation_effort="easy",
            weight=0.6,
        )

    def _build_spf_finding(self, posture: DnsSecurityPosture) -> ModuleFinding | None:
        """Return a MEDIUM finding when no SPF record is present.

        Args:
            posture: The DNS email security posture.

        Returns:
            ModuleFinding or None.
        """
        if posture.spf_record is not None:
            return None
        return ModuleFinding(
            finding_type="spf_missing",
            severity=Severity.MEDIUM,
            category="domain",
            title=f"No SPF record found for {posture.domain}",
            description=(
                f"The domain {posture.domain!r} has no SPF (Sender Policy Framework) "
                "record. Without SPF, anyone can send email appearing to originate "
                "from this domain, enabling impersonation and phishing attacks."
            ),
            platform="dns",
            evidence={
                "domain": posture.domain,
                "email_security_tier": posture.email_security_tier.value,
            },
            remediation_action=(
                "Add an SPF TXT record to your domain DNS "
                '(e.g., "v=spf1 include:_spf.google.com ~all").'
            ),
            remediation_effort="moderate",
            weight=0.5,
        )

    def _build_dmarc_finding(self, posture: DnsSecurityPosture) -> ModuleFinding | None:
        """Return a MEDIUM finding when no DMARC record is present.

        Args:
            posture: The DNS email security posture.

        Returns:
            ModuleFinding or None.
        """
        if posture.dmarc_record is not None:
            return None
        return ModuleFinding(
            finding_type="dmarc_missing",
            severity=Severity.MEDIUM,
            category="domain",
            title=f"No DMARC record found for {posture.domain}",
            description=(
                f"The domain {posture.domain!r} has no DMARC (Domain-based Message "
                "Authentication, Reporting, and Conformance) policy. Without DMARC, "
                "the domain is vulnerable to email spoofing even if SPF is present."
            ),
            platform="dns",
            evidence={
                "domain": posture.domain,
                "spf_present": posture.spf_record is not None,
                "email_security_tier": posture.email_security_tier.value,
            },
            remediation_action=(
                f"Add a DMARC TXT record at _dmarc.{posture.domain} "
                "with at minimum p=none to begin monitoring."
            ),
            remediation_effort="moderate",
            weight=0.4,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _detect_privacy(
    registrant_name: str | None,
    registrant_org: str | None,
) -> bool:
    """Return True if WHOIS fields indicate a privacy/proxy service.

    Treats the registration as privacy-protected when either the name or org
    contains a known privacy keyword, or when both fields are absent (which
    commonly indicates mandatory GDPR redaction).

    Args:
        registrant_name: Parsed registrant name, or None.
        registrant_org: Parsed registrant organization, or None.

    Returns:
        True if privacy protection is detected or data is fully absent.
    """
    if not registrant_name and not registrant_org:
        return True
    combined = " ".join(
        v.lower() for v in [registrant_name or "", registrant_org or ""]
    )
    return any(kw in combined for kw in _PRIVACY_KEYWORDS)


def _coerce_first(value: Any) -> str | None:
    """Return the first element if value is a list, or the value itself as a string.

    python-whois returns some fields as lists (multiple values) and others as
    plain strings. This normalizes both forms to a single string or None.

    Args:
        value: Raw field value from python-whois.

    Returns:
        String value or None.
    """
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value).strip() if value is not None else None


def _coerce_list(value: Any) -> list[str]:
    """Normalize a potentially list-or-string value to a list of strings.

    Args:
        value: Raw field value from python-whois (may be list, str, or None).

    Returns:
        List of non-empty strings.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if v]
    return [str(value).strip().lower()] if value else []


def _coerce_date(value: Any) -> datetime | None:
    """Extract the first datetime if value is a list, or return as-is.

    python-whois sometimes returns a list of datetimes for creation_date.

    Args:
        value: Raw date value from python-whois.

    Returns:
        A datetime object, or None.
    """
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, datetime):
        return value
    return None

"""Unit tests for the Domain Intelligence module (T3.2).

Tests cover:
  - Domain extraction from email addresses
  - WhoisClient: parsing, privacy heuristic, exception mapping
  - DNSAnalyzer: SPF/DMARC detection, tier classification, exception mapping
  - DomainIntelModule.execute(): findings, partial success, metadata
  - Privacy heuristic edge cases (_detect_privacy helper)

All network calls are mocked at the asyncio.to_thread boundary to avoid
real DNS/WHOIS lookups in unit tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from piea.modules.base import ScanInputs, Severity
from piea.modules.domain_intel import (
    DNSAnalyzer,
    DnsSecurityPosture,
    DomainIntelLookupError,
    DomainIntelModule,
    DomainIntelRateLimitError,
    DomainIntelTimeoutError,
    EmailSecurityTier,
    WhoisClient,
    WhoisData,
    _coerce_date,
    _coerce_first,
    _coerce_list,
    _detect_privacy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _whois_dict(
    name: str | None = "John Doe",
    org: str | None = None,
    registrar: str | None = "Example Registrar, LLC",
    creation_date: Any = None,
    expiration_date: Any = None,
    name_servers: Any = None,
) -> dict[str, Any]:
    """Build a minimal python-whois-like response dict."""
    return {
        "name": name,
        "org": org,
        "registrar": registrar,
        "creation_date": creation_date or datetime(2015, 6, 1),
        "expiration_date": expiration_date or datetime(2026, 6, 1),
        "name_servers": name_servers or ["ns1.example.com", "ns2.example.com"],
    }


def _make_posture(
    domain: str = "example.com",
    has_mx: bool = True,
    spf_record: str | None = "v=spf1 include:_spf.google.com ~all",
    dmarc_record: str | None = "v=DMARC1; p=reject; rua=mailto:dmarc@example.com",
    dmarc_policy: str | None = "reject",
    tier: EmailSecurityTier = EmailSecurityTier.STRONG,
) -> DnsSecurityPosture:
    """Build a DnsSecurityPosture for testing."""
    return DnsSecurityPosture(
        domain=domain,
        has_mx=has_mx,
        spf_record=spf_record,
        dmarc_record=dmarc_record,
        dmarc_policy=dmarc_policy,
        email_security_tier=tier,
    )


def _make_whois(
    domain: str = "example.com",
    registrant_name: str | None = "John Doe",
    registrant_org: str | None = None,
    privacy_protected: bool = False,
) -> WhoisData:
    """Build a WhoisData for testing."""
    return WhoisData(
        domain=domain,
        registrant_name=registrant_name,
        registrant_org=registrant_org,
        registration_date=datetime(2015, 6, 1),
        expiration_date=datetime(2026, 6, 1),
        registrar="Example Registrar",
        name_servers=["ns1.example.com"],
        privacy_protected=privacy_protected,
    )


# ---------------------------------------------------------------------------
# _detect_privacy
# ---------------------------------------------------------------------------


class TestDetectPrivacy:
    def test_both_none_returns_true(self):
        assert _detect_privacy(None, None) is True

    def test_privacy_keyword_in_name(self):
        assert _detect_privacy("WhoisGuard Protected", None) is True

    def test_privacy_keyword_in_org(self):
        assert _detect_privacy(None, "Contact Privacy Inc.") is True

    def test_redacted_for_privacy(self):
        assert _detect_privacy("REDACTED FOR PRIVACY", None) is True

    def test_protect_in_name(self):
        assert _detect_privacy("Domain Protection Services", None) is True

    def test_proxy_in_org(self):
        assert _detect_privacy(None, "Perfect Privacy LLC") is True

    def test_real_name_no_keywords_returns_false(self):
        assert _detect_privacy("John Doe", None) is False

    def test_real_name_and_org_no_keywords_returns_false(self):
        assert _detect_privacy("Jane Smith", "Acme Corp") is False

    def test_withheld_keyword(self):
        assert _detect_privacy("Withheld for Privacy", None) is True

    def test_not_disclosed_keyword(self):
        assert _detect_privacy("Not Disclosed", None) is True


# ---------------------------------------------------------------------------
# Helper functions: _coerce_first, _coerce_list, _coerce_date
# ---------------------------------------------------------------------------


class TestCoerceFirst:
    def test_none_returns_none(self):
        assert _coerce_first(None) is None

    def test_string_returned_as_is(self):
        assert _coerce_first("hello") == "hello"

    def test_list_returns_first(self):
        assert _coerce_first(["first", "second"]) == "first"

    def test_empty_list_returns_none(self):
        assert _coerce_first([]) is None


class TestCoerceList:
    def test_none_returns_empty(self):
        assert _coerce_list(None) == []

    def test_list_of_strings(self):
        result = _coerce_list(["NS1.EXAMPLE.COM", "ns2.example.com"])
        assert "ns1.example.com" in result

    def test_single_string(self):
        assert _coerce_list("ns1.example.com") == ["ns1.example.com"]


class TestCoerceDate:
    def test_none_returns_none(self):
        assert _coerce_date(None) is None

    def test_datetime_returned_directly(self):
        dt = datetime(2020, 1, 1)
        assert _coerce_date(dt) == dt

    def test_list_returns_first_datetime(self):
        dt = datetime(2020, 1, 1)
        assert _coerce_date([dt, datetime(2021, 1, 1)]) == dt

    def test_non_datetime_returns_none(self):
        assert _coerce_date("2020-01-01") is None


# ---------------------------------------------------------------------------
# DomainIntelModule._extract_domain
# ---------------------------------------------------------------------------


class TestExtractDomain:
    def test_valid_email(self):
        assert DomainIntelModule._extract_domain("user@example.com") == "example.com"

    def test_alternate_tld(self):
        assert DomainIntelModule._extract_domain("a@example.org") == "example.org"

    def test_no_at_sign_returns_none(self):
        assert DomainIntelModule._extract_domain("notanemail") is None

    def test_empty_domain_part_returns_none(self):
        assert DomainIntelModule._extract_domain("user@") is None

    def test_uppercase_normalized(self):
        assert DomainIntelModule._extract_domain("X@EXAMPLE.COM") == "example.com"

    def test_leading_trailing_whitespace_stripped(self):
        assert (
            DomainIntelModule._extract_domain("  user@example.com  ") == "example.com"
        )


# ---------------------------------------------------------------------------
# WhoisClient
# ---------------------------------------------------------------------------


class TestWhoisClient:
    @pytest.mark.asyncio
    async def test_lookup_returns_whois_data(self):
        client = WhoisClient()
        raw = _whois_dict(name="John Doe")
        with patch("asyncio.to_thread", new=AsyncMock(return_value=raw)):
            result = await client.lookup("example.com")
        assert isinstance(result, WhoisData)
        assert result.registrant_name == "John Doe"
        assert result.domain == "example.com"
        assert result.privacy_protected is False

    @pytest.mark.asyncio
    async def test_privacy_protected_heuristic_name(self):
        client = WhoisClient()
        raw = _whois_dict(name="WhoisGuard Protected")
        with patch("asyncio.to_thread", new=AsyncMock(return_value=raw)):
            result = await client.lookup("example.com")
        assert result.privacy_protected is True

    @pytest.mark.asyncio
    async def test_privacy_protected_heuristic_org(self):
        client = WhoisClient()
        raw = _whois_dict(name=None, org="Contact Privacy Inc.")
        with patch("asyncio.to_thread", new=AsyncMock(return_value=raw)):
            result = await client.lookup("example.com")
        assert result.privacy_protected is True

    @pytest.mark.asyncio
    async def test_privacy_not_protected_real_info(self):
        client = WhoisClient()
        raw = _whois_dict(name="Jane Smith", org="Acme Corp")
        with patch("asyncio.to_thread", new=AsyncMock(return_value=raw)):
            result = await client.lookup("example.com")
        assert result.privacy_protected is False
        assert result.registrant_name == "Jane Smith"

    @pytest.mark.asyncio
    async def test_lookup_timeout_raises_domain_timeout_error(self):
        client = WhoisClient()
        with patch(
            "asyncio.to_thread", new=AsyncMock(side_effect=TimeoutError("timed out"))
        ):
            with pytest.raises(DomainIntelTimeoutError):
                await client.lookup("example.com")

    @pytest.mark.asyncio
    async def test_lookup_not_found_raises_lookup_error(self):
        client = WhoisClient()
        exc = Exception("No match for EXAMPLE.COM")
        with patch("asyncio.to_thread", new=AsyncMock(side_effect=exc)):
            with pytest.raises(DomainIntelLookupError):
                await client.lookup("example.com")

    @pytest.mark.asyncio
    async def test_lookup_rate_limited_raises_rate_limit_error(self):
        client = WhoisClient()
        exc = Exception("Rate limit exceeded for this IP")
        with patch("asyncio.to_thread", new=AsyncMock(side_effect=exc)):
            with pytest.raises(DomainIntelRateLimitError):
                await client.lookup("example.com")

    @pytest.mark.asyncio
    async def test_lookup_none_response_raises_lookup_error(self):
        client = WhoisClient()
        with patch("asyncio.to_thread", new=AsyncMock(return_value=None)):
            with pytest.raises(DomainIntelLookupError):
                await client.lookup("example.com")

    @pytest.mark.asyncio
    async def test_lookup_missing_fields_handled(self):
        client = WhoisClient()
        raw = {
            "name": None,
            "org": None,
            "registrar": None,
            "creation_date": None,
            "expiration_date": None,
            "name_servers": None,
        }
        with patch("asyncio.to_thread", new=AsyncMock(return_value=raw)):
            result = await client.lookup("example.com")
        # Both fields None → treated as privacy protected
        assert result.privacy_protected is True
        assert result.registrant_name is None
        assert result.registrant_org is None
        assert result.name_servers == []

    @pytest.mark.asyncio
    async def test_list_creation_date_takes_first(self):
        client = WhoisClient()
        dt1 = datetime(2015, 1, 1)
        dt2 = datetime(2016, 1, 1)
        raw = _whois_dict(creation_date=[dt1, dt2])
        with patch("asyncio.to_thread", new=AsyncMock(return_value=raw)):
            result = await client.lookup("example.com")
        assert result.registration_date == dt1


# ---------------------------------------------------------------------------
# DNSAnalyzer
# ---------------------------------------------------------------------------


class TestDNSAnalyzerClassifyTier:
    """Unit tests for the synchronous _classify_tier helper."""

    def test_strong_with_reject(self):
        analyzer = DNSAnalyzer()
        tier, policy = analyzer._classify_tier("v=spf1 ~all", "v=DMARC1; p=reject")
        assert tier == EmailSecurityTier.STRONG
        assert policy == "reject"

    def test_strong_with_quarantine(self):
        analyzer = DNSAnalyzer()
        tier, policy = analyzer._classify_tier("v=spf1 ~all", "v=DMARC1; p=quarantine")
        assert tier == EmailSecurityTier.STRONG
        assert policy == "quarantine"

    def test_moderate_with_p_none(self):
        analyzer = DNSAnalyzer()
        tier, policy = analyzer._classify_tier("v=spf1 ~all", "v=DMARC1; p=none")
        assert tier == EmailSecurityTier.MODERATE
        assert policy == "none"

    def test_weak_spf_no_dmarc(self):
        analyzer = DNSAnalyzer()
        tier, policy = analyzer._classify_tier("v=spf1 ~all", None)
        assert tier == EmailSecurityTier.WEAK
        assert policy is None

    def test_none_tier_no_spf(self):
        analyzer = DNSAnalyzer()
        tier, policy = analyzer._classify_tier(None, None)
        assert tier == EmailSecurityTier.NONE

    def test_none_tier_dmarc_without_spf(self):
        # DMARC without SPF is still considered NONE tier
        analyzer = DNSAnalyzer()
        tier, policy = analyzer._classify_tier(None, "v=DMARC1; p=reject")
        assert tier == EmailSecurityTier.NONE


class TestDNSAnalyzerExtractDmarcPolicy:
    def test_reject_policy(self):
        analyzer = DNSAnalyzer()
        assert analyzer._extract_dmarc_policy("v=DMARC1; p=reject; rua=...") == "reject"

    def test_none_policy(self):
        analyzer = DNSAnalyzer()
        assert analyzer._extract_dmarc_policy("v=DMARC1; p=none") == "none"

    def test_quarantine_policy(self):
        analyzer = DNSAnalyzer()
        assert analyzer._extract_dmarc_policy("v=DMARC1; p=quarantine;") == "quarantine"

    def test_missing_p_returns_none(self):
        analyzer = DNSAnalyzer()
        assert analyzer._extract_dmarc_policy("v=DMARC1; adkim=r") is None

    def test_case_insensitive_match(self):
        analyzer = DNSAnalyzer()
        assert analyzer._extract_dmarc_policy("v=DMARC1; P=REJECT") == "reject"


class TestDNSAnalyzerAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_strong_spf_reject(self):
        analyzer = DNSAnalyzer()

        def side_effect(fn, *args):
            domain_arg = args[0] if args else ""
            if "_dmarc" in str(domain_arg):
                return ["v=DMARC1; p=reject"]
            if fn.__name__ == "_query_has_mx":
                return True
            return ["v=spf1 include:_spf.google.com ~all"]

        with patch("asyncio.to_thread", side_effect=AsyncMock(side_effect=side_effect)):
            posture = await analyzer.analyze("example.com")
        assert posture.email_security_tier == EmailSecurityTier.STRONG
        assert posture.dmarc_policy == "reject"

    @pytest.mark.asyncio
    async def test_analyze_strong_spf_quarantine(self):
        analyzer = DNSAnalyzer()
        call_count = [0]

        async def side_effect(fn, *args):
            call_count[0] += 1
            domain_arg = args[0] if args else ""
            if hasattr(fn, "__name__") and fn.__name__ == "_query_has_mx":
                return True
            if "_dmarc" in str(domain_arg):
                return ["v=DMARC1; p=quarantine"]
            return ["v=spf1 ~all"]

        with patch("asyncio.to_thread", side_effect=side_effect):
            posture = await analyzer.analyze("example.com")
        assert posture.email_security_tier == EmailSecurityTier.STRONG

    @pytest.mark.asyncio
    async def test_analyze_moderate(self):
        analyzer = DNSAnalyzer()

        async def side_effect(fn, *args):
            domain_arg = args[0] if args else ""
            if hasattr(fn, "__name__") and fn.__name__ == "_query_has_mx":
                return True
            if "_dmarc" in str(domain_arg):
                return ["v=DMARC1; p=none"]
            return ["v=spf1 ~all"]

        with patch("asyncio.to_thread", side_effect=side_effect):
            posture = await analyzer.analyze("example.com")
        assert posture.email_security_tier == EmailSecurityTier.MODERATE

    @pytest.mark.asyncio
    async def test_analyze_weak_no_dmarc(self):
        analyzer = DNSAnalyzer()

        async def side_effect(fn, *args):
            domain_arg = args[0] if args else ""
            if hasattr(fn, "__name__") and fn.__name__ == "_query_has_mx":
                return True
            if "_dmarc" in str(domain_arg):
                return []
            return ["v=spf1 ~all"]

        with patch("asyncio.to_thread", side_effect=side_effect):
            posture = await analyzer.analyze("example.com")
        assert posture.email_security_tier == EmailSecurityTier.WEAK
        assert posture.dmarc_record is None

    @pytest.mark.asyncio
    async def test_analyze_none_tier_no_spf_no_dmarc(self):
        analyzer = DNSAnalyzer()

        async def side_effect(fn, *args):
            if hasattr(fn, "__name__") and fn.__name__ == "_query_has_mx":
                return False
            return []

        with patch("asyncio.to_thread", side_effect=side_effect):
            posture = await analyzer.analyze("example.com")
        assert posture.email_security_tier == EmailSecurityTier.NONE
        assert posture.spf_record is None
        assert posture.dmarc_record is None

    @pytest.mark.asyncio
    async def test_analyze_timeout_raises(self):
        analyzer = DNSAnalyzer()
        with patch(
            "asyncio.to_thread",
            new=AsyncMock(side_effect=dns.exception.Timeout),
        ):
            with pytest.raises(DomainIntelTimeoutError):
                await analyzer.analyze("example.com")

    @pytest.mark.asyncio
    async def test_analyze_nxdomain_raises_lookup_error(self):
        analyzer = DNSAnalyzer()
        with patch(
            "asyncio.to_thread",
            new=AsyncMock(side_effect=dns.resolver.NXDOMAIN),
        ):
            with pytest.raises(DomainIntelLookupError):
                await analyzer.analyze("example.com")


# ---------------------------------------------------------------------------
# DomainIntelModule
# ---------------------------------------------------------------------------


class TestDomainIntelModuleExecute:
    def _make_module(
        self,
        whois_result: WhoisData | Exception | None = None,
        dns_result: DnsSecurityPosture | Exception | None = None,
    ) -> DomainIntelModule:
        """Build a DomainIntelModule with injected mock clients."""
        whois_client = MagicMock(spec=WhoisClient)
        dns_analyzer = MagicMock(spec=DNSAnalyzer)

        if isinstance(whois_result, Exception):
            whois_client.lookup = AsyncMock(side_effect=whois_result)
        elif whois_result is None:
            whois_client.lookup = AsyncMock(
                side_effect=DomainIntelLookupError("not found")
            )
        else:
            whois_client.lookup = AsyncMock(return_value=whois_result)

        if isinstance(dns_result, Exception):
            dns_analyzer.analyze = AsyncMock(side_effect=dns_result)
        elif dns_result is None:
            dns_analyzer.analyze = AsyncMock(
                side_effect=DomainIntelLookupError("not found")
            )
        else:
            dns_analyzer.analyze = AsyncMock(return_value=dns_result)

        return DomainIntelModule(whois_client=whois_client, dns_analyzer=dns_analyzer)

    @pytest.mark.asyncio
    async def test_execute_no_email_returns_failure(self):
        module = self._make_module()
        result = await module.execute(ScanInputs())
        assert result.success is False
        assert result.errors

    @pytest.mark.asyncio
    async def test_execute_invalid_email_format_returns_failure(self):
        module = self._make_module()
        result = await module.execute(ScanInputs(email="notanemail"))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_whois_high_finding_when_no_privacy(self):
        whois_data = _make_whois(registrant_name="John Doe", privacy_protected=False)
        posture = _make_posture()
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="john@example.com"))
        assert result.success is True
        whois_findings = [
            f for f in result.findings if f.finding_type == "whois_privacy_missing"
        ]
        assert len(whois_findings) == 1
        assert whois_findings[0].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_execute_no_whois_finding_when_privacy_protected(self):
        whois_data = _make_whois(
            registrant_name="WhoisGuard Protected", privacy_protected=True
        )
        posture = _make_posture()
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="user@example.com"))
        whois_findings = [
            f for f in result.findings if f.finding_type == "whois_privacy_missing"
        ]
        assert len(whois_findings) == 0

    @pytest.mark.asyncio
    async def test_execute_spf_missing_produces_medium_finding(self):
        whois_data = _make_whois(privacy_protected=True)
        posture = _make_posture(
            spf_record=None,
            dmarc_record=None,
            dmarc_policy=None,
            tier=EmailSecurityTier.NONE,
        )
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="user@example.com"))
        spf_findings = [f for f in result.findings if f.finding_type == "spf_missing"]
        assert len(spf_findings) == 1
        assert spf_findings[0].severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_execute_dmarc_missing_produces_medium_finding(self):
        whois_data = _make_whois(privacy_protected=True)
        posture = _make_posture(
            spf_record="v=spf1 ~all",
            dmarc_record=None,
            dmarc_policy=None,
            tier=EmailSecurityTier.WEAK,
        )
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="user@example.com"))
        dmarc_findings = [
            f for f in result.findings if f.finding_type == "dmarc_missing"
        ]
        assert len(dmarc_findings) == 1
        assert dmarc_findings[0].severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_execute_both_findings_on_none_tier(self):
        whois_data = _make_whois(privacy_protected=True)
        posture = _make_posture(
            spf_record=None,
            dmarc_record=None,
            dmarc_policy=None,
            tier=EmailSecurityTier.NONE,
        )
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="user@example.com"))
        types = {f.finding_type for f in result.findings}
        assert "spf_missing" in types
        assert "dmarc_missing" in types

    @pytest.mark.asyncio
    async def test_execute_strong_tier_no_security_findings(self):
        whois_data = _make_whois(privacy_protected=True)
        posture = _make_posture(tier=EmailSecurityTier.STRONG)
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="user@example.com"))
        security_findings = [
            f
            for f in result.findings
            if f.finding_type in {"spf_missing", "dmarc_missing"}
        ]
        assert len(security_findings) == 0

    @pytest.mark.asyncio
    async def test_execute_whois_timeout_partial_success(self):
        posture = _make_posture()
        module = self._make_module(
            whois_result=DomainIntelTimeoutError("timed out"),
            dns_result=posture,
        )
        result = await module.execute(ScanInputs(email="user@example.com"))
        assert result.success is True
        assert any("WHOIS" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_execute_dns_error_partial_success(self):
        whois_data = _make_whois(privacy_protected=True)
        module = self._make_module(
            whois_result=whois_data,
            dns_result=DomainIntelTimeoutError("timed out"),
        )
        result = await module.execute(ScanInputs(email="user@example.com"))
        assert result.success is True
        assert any("DNS" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_execute_both_fail_returns_false(self):
        module = self._make_module(
            whois_result=DomainIntelTimeoutError("timed out"),
            dns_result=DomainIntelTimeoutError("timed out"),
        )
        result = await module.execute(ScanInputs(email="user@example.com"))
        assert result.success is False
        assert len(result.errors) == 2

    @pytest.mark.asyncio
    async def test_execute_metadata_contains_domain(self):
        whois_data = _make_whois(privacy_protected=True)
        posture = _make_posture()
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="user@example.com"))
        assert result.metadata["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_execute_metadata_contains_tier_when_dns_succeeds(self):
        whois_data = _make_whois(privacy_protected=True)
        posture = _make_posture(tier=EmailSecurityTier.STRONG)
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="user@example.com"))
        assert result.metadata["email_security_tier"] == "strong"

    @pytest.mark.asyncio
    async def test_execute_metadata_tier_none_when_dns_fails(self):
        module = self._make_module(
            whois_result=_make_whois(privacy_protected=True),
            dns_result=DomainIntelLookupError("not found"),
        )
        result = await module.execute(ScanInputs(email="user@example.com"))
        assert result.metadata["email_security_tier"] is None

    @pytest.mark.asyncio
    async def test_module_name_is_domain_intel(self):
        module = DomainIntelModule()
        assert module.name == "domain_intel"

    @pytest.mark.asyncio
    async def test_execute_evidence_contains_domain(self):
        whois_data = _make_whois(registrant_name="Alice Corp", privacy_protected=False)
        posture = _make_posture()
        module = self._make_module(whois_result=whois_data, dns_result=posture)
        result = await module.execute(ScanInputs(email="alice@example.com"))
        whois_finding = next(
            f for f in result.findings if f.finding_type == "whois_privacy_missing"
        )
        assert whois_finding.evidence["domain"] == "example.com"

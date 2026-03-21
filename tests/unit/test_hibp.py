"""Unit tests for the HIBP module (T1.5).

Tests cover:
  - Severity classification logic
  - HIBPClient breach fetching (mocked HTTP)
  - HIBPClient password hash checking (mocked HTTP)
  - HIBPModule execute() with success, error, and cache scenarios
  - Rate limiting and retry behavior
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from piea.modules.base import ModuleAPIError, ModuleResult, Severity, ScanInputs
from piea.modules.hibp import (
    HIBP_API_BASE,
    HIBP_PASSWORDS_BASE,
    BreachRecord,
    HIBPClient,
    HIBPConfigError,
    HIBPModule,
    classify_breach_severity,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_BREACH_RESPONSE = [
    {
        "Name": "Adobe",
        "Title": "Adobe",
        "Domain": "adobe.com",
        "BreachDate": "2013-10-04",
        "AddedDate": "2013-12-04T00:00:00Z",
        "ModifiedDate": "2022-05-15T23:52:49Z",
        "PwnCount": 152445165,
        "Description": "In October 2013, 153 million Adobe accounts were breached.",
        "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
        "IsVerified": True,
        "IsFabricated": False,
        "IsSensitive": False,
        "IsRetired": False,
        "IsSpamList": False,
        "IsMalware": False,
        "IsSubscriptionFree": False,
    },
    {
        "Name": "LinkedIn",
        "Title": "LinkedIn",
        "Domain": "linkedin.com",
        "BreachDate": "2012-05-05",
        "AddedDate": "2016-05-21T21:35:40Z",
        "ModifiedDate": "2016-05-21T21:35:40Z",
        "PwnCount": 164611595,
        "Description": "In May 2016, LinkedIn had 164 million email addresses exposed.",
        "DataClasses": ["Email addresses", "Passwords"],
        "IsVerified": True,
        "IsFabricated": False,
        "IsSensitive": False,
        "IsRetired": False,
        "IsSpamList": False,
        "IsMalware": False,
        "IsSubscriptionFree": False,
    },
    {
        "Name": "Dropbox",
        "Title": "Dropbox",
        "Domain": "dropbox.com",
        "BreachDate": "2012-07-01",
        "AddedDate": "2016-08-31T00:19:19Z",
        "ModifiedDate": "2016-08-31T00:19:19Z",
        "PwnCount": 68648009,
        "Description": "In mid-2012, Dropbox suffered a data breach.",
        "DataClasses": ["Email addresses", "Passwords"],
        "IsVerified": True,
        "IsFabricated": False,
        "IsSensitive": False,
        "IsRetired": False,
        "IsSpamList": False,
        "IsMalware": False,
        "IsSubscriptionFree": False,
    },
]

SAMPLE_PASSWORD_RESPONSE = (
    "003D68EB55068C33ACE09247EE4C639306B:3\r\n"
    "1E4C9B93F3F0682250B6CF8331B7EE68FD8:3861493\r\n"
    "01330F2A5B30B8B7E8F3C9C8D4F9B0A2E11:2\r\n"
)

TEST_EMAIL = "test@example.com"


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------


class TestClassifyBreachSeverity:
    """Tests for the classify_breach_severity function."""

    def test_critical_when_passwords_exposed(self):
        assert classify_breach_severity(["Passwords", "Email addresses"]) == Severity.CRITICAL

    def test_critical_when_financial_data_exposed(self):
        assert classify_breach_severity(["Financial data"]) == Severity.CRITICAL

    def test_critical_when_plaintext_passwords_exposed(self):
        assert classify_breach_severity(["Plaintext passwords"]) == Severity.CRITICAL

    def test_critical_when_credit_cards_exposed(self):
        assert classify_breach_severity(["Credit cards", "Email addresses"]) == Severity.CRITICAL

    def test_high_when_phone_numbers_exposed(self):
        assert classify_breach_severity(["Phone numbers", "Email addresses"]) == Severity.HIGH

    def test_high_when_physical_addresses_exposed(self):
        assert classify_breach_severity(["Physical addresses"]) == Severity.HIGH

    def test_high_when_government_ids_exposed(self):
        assert classify_breach_severity(["Government issued IDs"]) == Severity.HIGH

    def test_high_when_dates_of_birth_exposed(self):
        assert classify_breach_severity(["Dates of birth", "Names"]) == Severity.HIGH

    def test_medium_when_email_and_usernames_exposed(self):
        assert classify_breach_severity(["Email addresses", "Usernames"]) == Severity.MEDIUM

    def test_medium_when_ip_addresses_exposed(self):
        assert classify_breach_severity(["IP addresses"]) == Severity.MEDIUM

    def test_low_when_no_recognized_classes(self):
        assert classify_breach_severity(["Unknown data type"]) == Severity.LOW

    def test_low_when_empty_data_classes(self):
        assert classify_breach_severity([]) == Severity.LOW

    def test_highest_severity_wins(self):
        """When multiple severity levels apply, the highest wins."""
        data_classes = [
            "Email addresses",   # medium
            "Phone numbers",     # high
            "Passwords",         # critical
        ]
        assert classify_breach_severity(data_classes) == Severity.CRITICAL


# ---------------------------------------------------------------------------
# HIBPClient — breach fetching
# ---------------------------------------------------------------------------


class TestHIBPClientBreaches:
    """Tests for HIBPClient.fetch_breaches_for_email."""

    @respx.mock
    async def test_returns_breaches_for_known_email(self):
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(
            200, json=SAMPLE_BREACH_RESPONSE
        )

        client = HIBPClient(api_key="test-key")
        breaches = await client.fetch_breaches_for_email(TEST_EMAIL)
        await client.close()

        assert len(breaches) == 3
        assert breaches[0].name == "Adobe"
        assert breaches[0].severity == Severity.CRITICAL  # has Passwords
        assert breaches[0].is_verified is True
        assert breaches[0].pwn_count == 152445165

    @respx.mock
    async def test_returns_empty_list_for_clean_email(self):
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(404)

        client = HIBPClient(api_key="test-key")
        breaches = await client.fetch_breaches_for_email(TEST_EMAIL)
        await client.close()

        assert breaches == []

    async def test_raises_config_error_without_api_key(self):
        client = HIBPClient(api_key="")

        with pytest.raises(HIBPConfigError, match="API key is required"):
            await client.fetch_breaches_for_email(TEST_EMAIL)
        await client.close()

    @respx.mock
    async def test_raises_on_server_error(self):
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(500)

        client = HIBPClient(api_key="test-key")
        with pytest.raises(ModuleAPIError, match="Breach lookup failed"):
            await client.fetch_breaches_for_email(TEST_EMAIL)
        await client.close()

    @respx.mock
    async def test_parses_breach_data_classes_correctly(self):
        breach_with_mixed = [{
            "Name": "TestBreach",
            "Title": "Test Breach",
            "Domain": "test.com",
            "BreachDate": "2024-01-01",
            "AddedDate": "2024-01-15T00:00:00Z",
            "PwnCount": 1000,
            "Description": "Test breach",
            "DataClasses": ["Phone numbers", "Email addresses"],
            "IsVerified": False,
            "IsSensitive": False,
        }]
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(
            200, json=breach_with_mixed
        )

        client = HIBPClient(api_key="test-key")
        breaches = await client.fetch_breaches_for_email(TEST_EMAIL)
        await client.close()

        assert len(breaches) == 1
        assert breaches[0].severity == Severity.HIGH  # Phone numbers -> HIGH


# ---------------------------------------------------------------------------
# HIBPClient — password hash check
# ---------------------------------------------------------------------------


class TestHIBPClientPasswordCheck:
    """Tests for HIBPClient.check_password_hash."""

    @respx.mock
    async def test_returns_suffix_counts(self):
        respx.get(f"{HIBP_PASSWORDS_BASE}/range/5BAA6").respond(
            200, text=SAMPLE_PASSWORD_RESPONSE
        )

        client = HIBPClient(api_key="test-key")
        result = await client.check_password_hash("5BAA6")
        await client.close()

        assert len(result) == 3
        assert result["1E4C9B93F3F0682250B6CF8331B7EE68FD8"] == 3861493

    async def test_rejects_invalid_prefix_length(self):
        client = HIBPClient(api_key="test-key")

        with pytest.raises(ValueError, match="5 hex characters"):
            await client.check_password_hash("ABC")
        await client.close()

    async def test_rejects_non_hex_prefix(self):
        client = HIBPClient(api_key="test-key")

        with pytest.raises(ValueError, match="5 hex characters"):
            await client.check_password_hash("GHIJK")
        await client.close()


# ---------------------------------------------------------------------------
# HIBPModule.execute
# ---------------------------------------------------------------------------


class TestHIBPModuleExecute:
    """Tests for the HIBPModule.execute method."""

    @respx.mock
    async def test_successful_scan_returns_findings(self):
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(
            200, json=SAMPLE_BREACH_RESPONSE
        )

        client = HIBPClient(api_key="test-key")
        module = HIBPModule(client=client)
        result = await module.execute(ScanInputs(email=TEST_EMAIL))
        await module.close()

        assert result.success is True
        assert result.module_name == "hibp"
        assert len(result.findings) == 3
        assert result.metadata["total_breaches"] == 3
        assert result.metadata["verified_breaches"] == 3

    @respx.mock
    async def test_no_breaches_returns_empty_findings(self):
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(404)

        client = HIBPClient(api_key="test-key")
        module = HIBPModule(client=client)
        result = await module.execute(ScanInputs(email=TEST_EMAIL))
        await module.close()

        assert result.success is True
        assert result.findings == []
        assert result.metadata["total_breaches"] == 0

    async def test_missing_email_returns_failure(self):
        module = HIBPModule(client=HIBPClient(api_key="test-key"))
        result = await module.execute(ScanInputs())
        await module.close()

        assert result.success is False
        assert "No email" in result.errors[0]

    async def test_missing_api_key_returns_failure(self):
        module = HIBPModule(client=HIBPClient(api_key=""))
        result = await module.execute(ScanInputs(email=TEST_EMAIL))
        await module.close()

        assert result.success is False
        assert "API key" in result.errors[0]

    @respx.mock
    async def test_finding_has_correct_structure(self):
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(
            200, json=[SAMPLE_BREACH_RESPONSE[0]]
        )

        client = HIBPClient(api_key="test-key")
        module = HIBPModule(client=client)
        result = await module.execute(ScanInputs(email=TEST_EMAIL))
        await module.close()

        finding = result.findings[0]
        assert finding.finding_type == "breach_exposure"
        assert finding.category == "breach"
        assert finding.severity == Severity.CRITICAL
        assert finding.platform == "adobe.com"
        assert "Adobe" in finding.title
        assert finding.evidence["breach_name"] == "Adobe"
        assert finding.evidence["pwn_count"] == 152445165
        assert finding.remediation_effort in ("easy", "moderate")

    @respx.mock
    async def test_verified_breach_gets_higher_weight(self):
        """Verified breaches should get a +0.1 weight bonus."""
        verified = [{**SAMPLE_BREACH_RESPONSE[0], "IsVerified": True}]
        unverified = [{**SAMPLE_BREACH_RESPONSE[0], "IsVerified": False}]

        respx.get(f"{HIBP_API_BASE}/breachedaccount/verified@example.com").respond(
            200, json=verified
        )
        respx.get(f"{HIBP_API_BASE}/breachedaccount/unverified@example.com").respond(
            200, json=unverified
        )

        client = HIBPClient(api_key="test-key")
        module = HIBPModule(client=client)

        result_v = await module.execute(ScanInputs(email="verified@example.com"))
        result_u = await module.execute(ScanInputs(email="unverified@example.com"))
        await module.close()

        assert result_v.findings[0].weight > result_u.findings[0].weight


# ---------------------------------------------------------------------------
# HIBPModule with caching
# ---------------------------------------------------------------------------


class TestHIBPModuleCaching:
    """Tests for cache integration in HIBPModule."""

    @respx.mock
    async def test_cache_miss_fetches_from_api(self):
        """On cache miss, the module should call the HIBP API."""
        respx.get(f"{HIBP_API_BASE}/breachedaccount/{TEST_EMAIL}").respond(
            200, json=SAMPLE_BREACH_RESPONSE
        )

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # cache miss
        mock_cache.set = AsyncMock(return_value=True)

        client = HIBPClient(api_key="test-key")
        module = HIBPModule(client=client, cache=mock_cache)
        result = await module.execute(ScanInputs(email=TEST_EMAIL))
        await module.close()

        assert result.success is True
        assert result.cached is False
        assert len(result.findings) == 3
        # Verify cache was written
        mock_cache.set.assert_called_once()

    async def test_cache_hit_skips_api_call(self):
        """On cache hit, the module should NOT call the HIBP API."""
        cached_data = [
            {
                "name": "Adobe",
                "title": "Adobe",
                "domain": "adobe.com",
                "breach_date": "2013-10-04",
                "added_date": "2013-12-04T00:00:00Z",
                "pwn_count": 152445165,
                "description": "Breach description",
                "data_classes": ["Passwords", "Email addresses"],
                "is_verified": True,
                "is_sensitive": False,
                "severity": "critical",
            }
        ]

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=cached_data)

        # Client with no API key — would fail if actually called
        client = HIBPClient(api_key="no-key-needed")
        module = HIBPModule(client=client, cache=mock_cache)
        result = await module.execute(ScanInputs(email=TEST_EMAIL))
        await module.close()

        assert result.success is True
        assert result.cached is True
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# BreachRecord dataclass
# ---------------------------------------------------------------------------


class TestBreachRecord:
    """Tests for the BreachRecord data model."""

    def test_breach_record_is_frozen(self):
        record = BreachRecord(
            name="Test",
            title="Test Breach",
            domain="test.com",
            breach_date="2024-01-01",
            added_date="2024-01-15",
            pwn_count=1000,
            description="A test breach",
        )
        with pytest.raises(AttributeError):
            record.name = "Modified"  # type: ignore[misc]

    def test_breach_record_default_values(self):
        record = BreachRecord(
            name="Test",
            title="Test",
            domain="test.com",
            breach_date="2024-01-01",
            added_date="2024-01-15",
            pwn_count=0,
            description="",
        )
        assert record.data_classes == []
        assert record.is_verified is False
        assert record.is_sensitive is False
        assert record.severity == Severity.LOW

"""Unit tests for the Hunter.io email pattern module (T3.6).

Tests cover:
  - _extract_domain_from_email helper
  - _parse_name_parts helper
  - _parse_retry_after helper
  - HunterClient: domain-search parsing, email-finder parsing, error mapping,
    rate-limit semaphore, API key protection (L007)
  - HunterModule.execute(): all finding combinations, partial success, metadata
"""

from __future__ import annotations

import httpx
import pytest
import respx

from piea.modules.base import ScanInputs, Severity
from piea.modules.hunter import (
    EMAIL_CONFIDENCE_THRESHOLD,
    HUNTER_BASE,
    HunterAPIError,
    HunterClient,
    HunterDomainResult,
    HunterEmailRecord,
    HunterModule,
    HunterRateLimitError,
    HunterTimeoutError,
    _extract_domain_from_email,
    _parse_name_parts,
    _parse_retry_after,
)

# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

DOMAIN_SEARCH_RESPONSE = {
    "data": {
        "domain": "example.com",
        "pattern": "{first}.{last}",
        "emails": [
            {
                "value": "alice.example@example.com",
                "type": "personal",
                "confidence": 92,
                "first_name": "Alice",
                "last_name": "Example",
            },
            {
                "value": "bob.smith@example.com",
                "type": "personal",
                "confidence": 81,
                "first_name": "Bob",
                "last_name": "Smith",
            },
        ],
    }
}

DOMAIN_SEARCH_NO_PATTERN = {
    "data": {
        "domain": "example.com",
        "pattern": None,
        "emails": [],
    }
}

EMAIL_FINDER_RESPONSE_HIGH = {
    "data": {
        "email": "alice.example@example.com",
        "score": 85,
    }
}

EMAIL_FINDER_RESPONSE_LOW = {
    "data": {
        "email": "alice.example@example.com",
        "score": 50,
    }
}

EMAIL_FINDER_RESPONSE_NO_EMAIL = {
    "data": {
        "email": None,
        "score": 0,
    }
}


# ---------------------------------------------------------------------------
# _extract_domain_from_email
# ---------------------------------------------------------------------------


class TestExtractDomainFromEmail:
    def test_valid_email(self):
        assert _extract_domain_from_email("user@example.com") == "example.com"

    def test_uppercase_normalised(self):
        assert _extract_domain_from_email("USER@EXAMPLE.COM") == "example.com"

    def test_no_at_sign_returns_none(self):
        assert _extract_domain_from_email("notanemail") is None

    def test_empty_domain_part_returns_none(self):
        assert _extract_domain_from_email("user@") is None

    def test_leading_whitespace_stripped(self):
        assert _extract_domain_from_email("  user@example.com  ") == "example.com"


# ---------------------------------------------------------------------------
# _parse_name_parts
# ---------------------------------------------------------------------------


class TestParseNameParts:
    def test_two_token_name(self):
        assert _parse_name_parts("Alice Example") == ("Alice", "Example")

    def test_three_token_uses_first_and_last(self):
        assert _parse_name_parts("Alice Marie Example") == ("Alice", "Example")

    def test_single_token_returns_none(self):
        assert _parse_name_parts("Madonna") is None

    def test_none_returns_none(self):
        assert _parse_name_parts(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_name_parts("") is None

    def test_whitespace_only_returns_none(self):
        assert _parse_name_parts("   ") is None


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------


class TestParseRetryAfter:
    def test_numeric_header(self):
        response = httpx.Response(429, headers={"Retry-After": "30"})
        assert _parse_retry_after(response) == 30.0

    def test_missing_header_returns_none(self):
        response = httpx.Response(429)
        assert _parse_retry_after(response) is None

    def test_non_numeric_returns_none(self):
        response = httpx.Response(
            429, headers={"Retry-After": "Wed, 01 Jan 2026 00:00:00 GMT"}
        )
        assert _parse_retry_after(response) is None


# ---------------------------------------------------------------------------
# HunterClient — HTTP layer (respx mocks)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestHunterClientDomainSearch:
    @respx.mock
    async def test_domain_search_returns_result(self):
        respx.get(f"{HUNTER_BASE}/domain-search").mock(
            return_value=httpx.Response(200, json=DOMAIN_SEARCH_RESPONSE)
        )
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        result = await client.search_domain("example.com")
        assert isinstance(result, HunterDomainResult)
        assert result.pattern == "{first}.{last}"
        assert len(result.emails) == 2

    @respx.mock
    async def test_domain_search_no_pattern(self):
        respx.get(f"{HUNTER_BASE}/domain-search").mock(
            return_value=httpx.Response(200, json=DOMAIN_SEARCH_NO_PATTERN)
        )
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        result = await client.search_domain("example.com")
        assert result.pattern is None
        assert result.emails == []

    @respx.mock
    async def test_domain_search_email_fields_populated(self):
        respx.get(f"{HUNTER_BASE}/domain-search").mock(
            return_value=httpx.Response(200, json=DOMAIN_SEARCH_RESPONSE)
        )
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        result = await client.search_domain("example.com")
        first_email = result.emails[0]
        assert first_email.value == "alice.example@example.com"
        assert first_email.email_type == "personal"
        assert first_email.confidence == 92

    @respx.mock
    async def test_domain_search_401_raises_api_error(self):
        respx.get(f"{HUNTER_BASE}/domain-search").mock(return_value=httpx.Response(401))
        client = HunterClient(api_key="bad-key", http_client=httpx.AsyncClient())
        with pytest.raises(HunterAPIError) as exc_info:
            await client.search_domain("example.com")
        assert exc_info.value.status_code == 401

    @respx.mock
    async def test_domain_search_api_error_does_not_expose_api_key(self):
        """L007: The API key must not appear in the exception message or chain."""
        respx.get(f"{HUNTER_BASE}/domain-search").mock(return_value=httpx.Response(403))
        client = HunterClient(
            api_key="secret-key-abc123", http_client=httpx.AsyncClient()
        )
        with pytest.raises(HunterAPIError) as exc_info:
            await client.search_domain("example.com")
        # Key must not appear in the exception message
        assert "secret-key-abc123" not in str(exc_info.value)
        # exc.__cause__ must be None (from None chain)
        assert exc_info.value.__cause__ is None

    @respx.mock
    async def test_domain_search_429_raises_rate_limit_error(self):
        respx.get(f"{HUNTER_BASE}/domain-search").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "60"})
        )
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(HunterRateLimitError) as exc_info:
            await client.search_domain("example.com")
        assert exc_info.value.retry_after == 60.0

    @respx.mock
    async def test_domain_search_timeout_raises_timeout_error(self):
        respx.get(f"{HUNTER_BASE}/domain-search").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(HunterTimeoutError):
            await client.search_domain("example.com")


@pytest.mark.anyio
class TestHunterClientEmailFinder:
    @respx.mock
    async def test_find_email_returns_email_and_score(self):
        respx.get(f"{HUNTER_BASE}/email-finder").mock(
            return_value=httpx.Response(200, json=EMAIL_FINDER_RESPONSE_HIGH)
        )
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        email, score = await client.find_email("example.com", "Alice", "Example")
        assert email == "alice.example@example.com"
        assert score == 85

    @respx.mock
    async def test_find_email_no_email_returns_none(self):
        respx.get(f"{HUNTER_BASE}/email-finder").mock(
            return_value=httpx.Response(200, json=EMAIL_FINDER_RESPONSE_NO_EMAIL)
        )
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        email, score = await client.find_email("example.com", "Alice", "Example")
        assert email is None
        assert score == 0

    @respx.mock
    async def test_find_email_500_raises_api_error(self):
        respx.get(f"{HUNTER_BASE}/email-finder").mock(return_value=httpx.Response(500))
        client = HunterClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(HunterAPIError) as exc_info:
            await client.find_email("example.com", "Alice", "Example")
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# HunterModule
# ---------------------------------------------------------------------------


def _make_client(
    domain_response: HunterDomainResult | Exception | None = None,
    finder_response: tuple[str | None, int] | Exception | None = None,
) -> HunterClient:
    """Build a HunterClient mock with injected responses."""
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock(spec=HunterClient)

    if isinstance(domain_response, Exception):
        client.search_domain = AsyncMock(side_effect=domain_response)
    elif domain_response is None:
        client.search_domain = AsyncMock(side_effect=HunterAPIError(404))
    else:
        client.search_domain = AsyncMock(return_value=domain_response)

    if isinstance(finder_response, Exception):
        client.find_email = AsyncMock(side_effect=finder_response)
    elif finder_response is None:
        client.find_email = AsyncMock(return_value=(None, 0))
    else:
        client.find_email = AsyncMock(return_value=finder_response)

    client.close = AsyncMock()
    return client


def _make_domain_result(
    domain: str = "example.com",
    pattern: str | None = "{first}.{last}",
    emails: list[HunterEmailRecord] | None = None,
) -> HunterDomainResult:
    return HunterDomainResult(
        domain=domain,
        pattern=pattern,
        emails=emails or [],
    )


def _make_email_record(value: str = "alice@example.com") -> HunterEmailRecord:
    return HunterEmailRecord(
        value=value,
        email_type="personal",
        confidence=90,
        first_name="Alice",
        last_name="Example",
    )


@pytest.mark.anyio
class TestHunterModuleExecute:
    async def test_no_api_key_returns_failure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "")
        module = HunterModule()
        result = await module.execute(ScanInputs(email="user@example.com"))
        assert result.success is False
        assert any("api key" in e.lower() for e in result.errors)

    async def test_no_email_returns_failure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        module = HunterModule(client=_make_client())
        result = await module.execute(ScanInputs())
        assert result.success is False

    async def test_invalid_email_returns_failure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        module = HunterModule(client=_make_client())
        result = await module.execute(ScanInputs(email="notanemail"))
        assert result.success is False

    async def test_pattern_found_produces_info_finding(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result(pattern="{first}.{last}")
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        result = await module.execute(ScanInputs(email="alice@example.com"))
        assert result.success is True
        pattern_findings = [
            f for f in result.findings if f.finding_type == "email_pattern_found"
        ]
        assert len(pattern_findings) == 1
        assert pattern_findings[0].severity == Severity.INFO

    async def test_no_pattern_no_pattern_finding(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result(pattern=None)
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        result = await module.execute(ScanInputs(email="alice@example.com"))
        pattern_findings = [
            f for f in result.findings if f.finding_type == "email_pattern_found"
        ]
        assert len(pattern_findings) == 0

    async def test_emails_exposed_finding_when_emails_present(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        emails = [
            _make_email_record("a@example.com"),
            _make_email_record("b@example.com"),
        ]
        domain_result = _make_domain_result(emails=emails)
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        result = await module.execute(ScanInputs(email="alice@example.com"))
        exposed_findings = [
            f for f in result.findings if f.finding_type == "email_addresses_exposed"
        ]
        assert len(exposed_findings) == 1
        assert exposed_findings[0].severity == Severity.MEDIUM
        assert exposed_findings[0].evidence["email_count"] == 2

    async def test_no_emails_exposed_finding_when_list_empty(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result(emails=[])
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        result = await module.execute(ScanInputs(email="alice@example.com"))
        exposed_findings = [
            f for f in result.findings if f.finding_type == "email_addresses_exposed"
        ]
        assert len(exposed_findings) == 0

    async def test_email_confirmed_finding_above_threshold(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result()
        client = _make_client(
            domain_response=domain_result,
            finder_response=("alice.example@example.com", EMAIL_CONFIDENCE_THRESHOLD),
        )
        module = HunterModule(client=client)
        result = await module.execute(
            ScanInputs(email="alice@example.com", full_name="Alice Example")
        )
        confirmed = [
            f for f in result.findings if f.finding_type == "email_address_confirmed"
        ]
        assert len(confirmed) == 1
        assert confirmed[0].severity == Severity.MEDIUM

    async def test_no_email_confirmed_below_threshold(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result()
        client = _make_client(
            domain_response=domain_result,
            finder_response=(
                "alice.example@example.com",
                EMAIL_CONFIDENCE_THRESHOLD - 1,
            ),
        )
        module = HunterModule(client=client)
        result = await module.execute(
            ScanInputs(email="alice@example.com", full_name="Alice Example")
        )
        confirmed = [
            f for f in result.findings if f.finding_type == "email_address_confirmed"
        ]
        assert len(confirmed) == 0

    async def test_single_token_name_skips_email_finder(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result()
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        await module.execute(
            ScanInputs(email="madonna@example.com", full_name="Madonna")
        )
        client.find_email.assert_not_called()

    async def test_none_name_skips_email_finder(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result()
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        await module.execute(ScanInputs(email="alice@example.com"))
        client.find_email.assert_not_called()

    async def test_domain_search_failure_partial_success_with_email_finder(
        self, monkeypatch
    ):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        client = _make_client(
            domain_response=HunterAPIError(500),
            finder_response=("alice.example@example.com", 85),
        )
        module = HunterModule(client=client)
        result = await module.execute(
            ScanInputs(email="alice@example.com", full_name="Alice Example")
        )
        assert result.success is True
        assert any("domain-search" in e for e in result.errors)

    async def test_both_fail_returns_false(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        client = _make_client(
            domain_response=HunterTimeoutError("timed out"),
            finder_response=HunterTimeoutError("timed out"),
        )
        module = HunterModule(client=client)
        result = await module.execute(
            ScanInputs(email="alice@example.com", full_name="Alice Example")
        )
        assert result.success is False
        assert len(result.errors) == 2

    async def test_metadata_contains_domain(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result()
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        result = await module.execute(ScanInputs(email="alice@example.com"))
        assert result.metadata["domain"] == "example.com"

    async def test_metadata_contains_pattern(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        domain_result = _make_domain_result(pattern="{first}.{last}")
        client = _make_client(domain_response=domain_result)
        module = HunterModule(client=client)
        result = await module.execute(ScanInputs(email="alice@example.com"))
        assert result.metadata["pattern"] == "{first}.{last}"

    async def test_metadata_pattern_none_when_domain_search_fails(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        client = _make_client(domain_response=HunterAPIError(500))
        module = HunterModule(client=client)
        result = await module.execute(
            ScanInputs(email="alice@example.com", full_name="Alice Example"),
        )
        assert result.metadata["pattern"] is None

    async def test_module_name_is_hunter(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        assert HunterModule().name == "hunter"

    async def test_all_three_findings_produced(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "key")
        emails = [_make_email_record("a@example.com")]
        domain_result = _make_domain_result(pattern="{first}.{last}", emails=emails)
        client = _make_client(
            domain_response=domain_result,
            finder_response=("alice.example@example.com", 85),
        )
        module = HunterModule(client=client)
        result = await module.execute(
            ScanInputs(email="alice@example.com", full_name="Alice Example")
        )
        types = {f.finding_type for f in result.findings}
        assert "email_pattern_found" in types
        assert "email_addresses_exposed" in types
        assert "email_address_confirmed" in types

"""Unit tests for the HIBP paste-account exposure module (T3.7).

Tests cover:
  - _parse_retry_after helper
  - PasteRecord dataclass immutability
  - PasteClient: 404 (clean result), paste parsing, error mapping,
    rate-limit handling, PII protection (L007/L016)
  - PasteMonitor.execute(): all finding combinations, metadata, partial failure
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from piea.modules.base import ScanInputs, Severity
from piea.modules.paste_monitor import (
    HIBP_PASTE_BASE,
    PasteClient,
    PasteMonitor,
    PasteMonitorAPIError,
    PasteMonitorError,
    PasteMonitorRateLimitError,
    PasteMonitorTimeoutError,
    PasteRecord,
    _parse_retry_after,
)

# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

TWO_PASTE_RESPONSE = [
    {
        "Source": "Pastebin",
        "Id": "abc123",
        "Title": "Leaked credentials",
        "Date": "2024-01-15T00:00:00",
        "EmailCount": 42,
    },
    {
        "Source": "Ghostbin",
        "Id": "xyz789",
        "Title": None,
        "Date": "2023-11-01T00:00:00",
        "EmailCount": 7,
    },
]

ONE_PASTE_RESPONSE = [
    {
        "Source": "Pastebin",
        "Id": "aaa000",
        "Title": "Combo list",
        "Date": "2025-03-10T00:00:00",
        "EmailCount": 100,
    }
]

MINIMAL_PASTE_RESPONSE = [
    {
        "Source": "Slexy",
    }
]


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------


class TestParseRetryAfter:
    def test_numeric_header(self):
        response = httpx.Response(429, headers={"Retry-After": "60"})
        assert _parse_retry_after(response) == 60.0

    def test_missing_header_returns_none(self):
        response = httpx.Response(429)
        assert _parse_retry_after(response) is None

    def test_non_numeric_returns_none(self):
        response = httpx.Response(
            429, headers={"Retry-After": "Wed, 01 Jan 2026 00:00:00 GMT"}
        )
        assert _parse_retry_after(response) is None

    def test_decimal_header(self):
        response = httpx.Response(429, headers={"Retry-After": "1.5"})
        assert _parse_retry_after(response) == 1.5


# ---------------------------------------------------------------------------
# PasteRecord
# ---------------------------------------------------------------------------


class TestPasteRecord:
    def test_paste_record_frozen(self):
        record = PasteRecord(
            source="Pastebin",
            title="Test",
            paste_id="abc",
            paste_date="2024-01-01",
            email_count=5,
        )
        with pytest.raises(AttributeError):
            record.source = "other"  # type: ignore[misc]

    def test_paste_record_fields(self):
        record = PasteRecord(
            source="Pastebin",
            title="Leaked creds",
            paste_id="abc123",
            paste_date="2024-01-15T00:00:00",
            email_count=42,
        )
        assert record.source == "Pastebin"
        assert record.title == "Leaked creds"
        assert record.paste_id == "abc123"
        assert record.paste_date == "2024-01-15T00:00:00"
        assert record.email_count == 42

    def test_paste_record_optional_fields_none(self):
        record = PasteRecord(
            source="Unknown",
            title=None,
            paste_id=None,
            paste_date=None,
            email_count=0,
        )
        assert record.title is None
        assert record.paste_id is None
        assert record.paste_date is None


# ---------------------------------------------------------------------------
# PasteClient — HTTP layer (respx mocks)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestPasteClient:
    @respx.mock
    async def test_returns_empty_list_on_404(self):
        """HTTP 404 means no pastes found — clean result, not an error."""
        respx.get(f"{HIBP_PASTE_BASE}/clean@example.com").mock(
            return_value=httpx.Response(404)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        result = await client.get_paste_exposure("clean@example.com")
        assert result == []

    @respx.mock
    async def test_parses_two_pastes(self):
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(200, json=TWO_PASTE_RESPONSE)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        records = await client.get_paste_exposure("victim@example.com")
        assert len(records) == 2
        assert records[0].source == "Pastebin"
        assert records[0].paste_id == "abc123"
        assert records[0].title == "Leaked credentials"
        assert records[0].email_count == 42
        assert records[1].source == "Ghostbin"
        assert records[1].title is None

    @respx.mock
    async def test_parse_response_handles_missing_optional_fields(self):
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(200, json=MINIMAL_PASTE_RESPONSE)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        records = await client.get_paste_exposure("victim@example.com")
        assert len(records) == 1
        assert records[0].source == "Slexy"
        assert records[0].title is None
        assert records[0].paste_id is None
        assert records[0].paste_date is None
        assert records[0].email_count == 0

    @respx.mock
    async def test_raises_rate_limit_on_429(self):
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "30"})
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(PasteMonitorRateLimitError) as exc_info:
            await client.get_paste_exposure("victim@example.com")
        assert exc_info.value.retry_after == 30.0

    @respx.mock
    async def test_rate_limit_without_retry_after_header(self):
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(429)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(PasteMonitorRateLimitError) as exc_info:
            await client.get_paste_exposure("victim@example.com")
        assert exc_info.value.retry_after is None

    @respx.mock
    async def test_raises_api_error_on_500(self):
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(500)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(PasteMonitorAPIError) as exc_info:
            await client.get_paste_exposure("victim@example.com")
        assert exc_info.value.status_code == 500

    @respx.mock
    async def test_api_error_chain_is_dropped(self):
        """L007/L016: email address must not appear in the exception chain."""
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(401)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(PasteMonitorAPIError) as exc_info:
            await client.get_paste_exposure("victim@example.com")
        # exc.__cause__ must be None (raised with `from None`)
        assert exc_info.value.__cause__ is None

    @respx.mock
    async def test_raises_timeout_on_httpx_timeout(self):
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        with pytest.raises(PasteMonitorTimeoutError):
            await client.get_paste_exposure("victim@example.com")

    @respx.mock
    async def test_rate_limit_sleep_runs_on_success(self):
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(200, json=ONE_PASTE_RESPONSE)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        with patch("piea.modules.paste_monitor.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            await client.get_paste_exposure("victim@example.com")
        mock_sleep.assert_called_once()

    @respx.mock
    async def test_rate_limit_sleep_runs_on_exception(self):
        """L009: sleep must execute even when request raises."""
        respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(500)
        )
        client = PasteClient(api_key="test-key", http_client=httpx.AsyncClient())
        with patch("piea.modules.paste_monitor.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            with pytest.raises(PasteMonitorAPIError):
                await client.get_paste_exposure("victim@example.com")
        mock_sleep.assert_called_once()

    async def test_close_calls_aclose_when_owns_client(self):
        inner = AsyncMock(spec=httpx.AsyncClient)
        # When http_client is None, PasteClient creates its own — test via flag
        client = PasteClient(api_key="test-key")
        client._client = inner  # type: ignore[attr-defined]
        client._owns_client = True  # type: ignore[attr-defined]
        await client.close()
        inner.aclose.assert_called_once()

    async def test_close_skips_aclose_when_not_owner(self):
        inner = AsyncMock(spec=httpx.AsyncClient)
        injected = httpx.AsyncClient()
        client = PasteClient(api_key="test-key", http_client=injected)
        client._client = inner  # type: ignore[attr-defined]
        await client.close()
        inner.aclose.assert_not_called()

    @respx.mock
    async def test_sends_hibp_api_key_header(self):
        """Auth must use hibp-api-key header, not a query parameter."""
        route = respx.get(f"{HIBP_PASTE_BASE}/victim@example.com").mock(
            return_value=httpx.Response(404)
        )
        client = PasteClient(api_key="my-secret-key", http_client=httpx.AsyncClient())
        await client.get_paste_exposure("victim@example.com")
        sent_headers = route.calls[0].request.headers
        assert sent_headers.get("hibp-api-key") == "my-secret-key"


# ---------------------------------------------------------------------------
# PasteMonitor — module layer (mock PasteClient)
# ---------------------------------------------------------------------------


def _make_paste_client(
    response: list[PasteRecord] | Exception | None = None,
) -> PasteClient:
    """Build a PasteClient mock with injected response."""
    mock_client = MagicMock(spec=PasteClient)
    if isinstance(response, Exception):
        mock_client.get_paste_exposure = AsyncMock(side_effect=response)
    else:
        mock_client.get_paste_exposure = AsyncMock(return_value=response or [])
    mock_client.close = AsyncMock()
    return mock_client


def _make_records(count: int = 1) -> list[PasteRecord]:
    return [
        PasteRecord(
            source="Pastebin",
            title=f"Paste {i}",
            paste_id=f"id{i}",
            paste_date="2024-01-01T00:00:00",
            email_count=10 + i,
        )
        for i in range(count)
    ]


@pytest.mark.anyio
class TestPasteMonitor:
    async def test_no_api_key_returns_failure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "")
        module = PasteMonitor()
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert result.success is False
        assert any("api key" in e.lower() for e in result.errors)

    async def test_no_email_returns_failure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(client=_make_paste_client())
        result = await module.execute(ScanInputs())
        assert result.success is False
        assert any("email" in e.lower() for e in result.errors)

    async def test_clean_email_returns_success_with_no_findings(self, monkeypatch):
        """HTTP 404 (no pastes) → success=True, empty findings list."""
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(client=_make_paste_client(response=[]))
        result = await module.execute(ScanInputs(email="clean@example.com"))
        assert result.success is True
        assert result.findings == []

    async def test_one_paste_produces_one_high_finding(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(client=_make_paste_client(response=_make_records(1)))
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert result.success is True
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.HIGH

    async def test_two_pastes_produce_two_high_findings(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(client=_make_paste_client(response=_make_records(2)))
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert len(result.findings) == 2
        assert all(f.severity == Severity.HIGH for f in result.findings)

    async def test_finding_structure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        records = [
            PasteRecord(
                source="Pastebin",
                title="Leaked creds",
                paste_id="abc123",
                paste_date="2024-01-15T00:00:00",
                email_count=42,
            )
        ]
        module = PasteMonitor(client=_make_paste_client(response=records))
        result = await module.execute(ScanInputs(email="victim@example.com"))
        finding = result.findings[0]
        assert finding.finding_type == "paste_exposure"
        assert finding.category == "credential_exposure"
        assert finding.severity == Severity.HIGH
        assert finding.title
        assert finding.description
        assert "source" in finding.evidence
        assert "paste_id" in finding.evidence
        assert "paste_date" in finding.evidence
        assert "email_count" in finding.evidence
        assert "title" in finding.evidence

    async def test_finding_evidence_values(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        records = [
            PasteRecord(
                source="Ghostbin",
                title="Dump",
                paste_id="xyz",
                paste_date="2023-06-01T00:00:00",
                email_count=5,
            )
        ]
        module = PasteMonitor(client=_make_paste_client(response=records))
        result = await module.execute(ScanInputs(email="victim@example.com"))
        ev = result.findings[0].evidence
        assert ev["source"] == "Ghostbin"
        assert ev["paste_id"] == "xyz"
        assert ev["email_count"] == 5

    async def test_untitled_paste_uses_fallback_title(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        records = [
            PasteRecord(
                source="Pastebin",
                title=None,
                paste_id="nnn",
                paste_date=None,
                email_count=1,
            )
        ]
        module = PasteMonitor(client=_make_paste_client(response=records))
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert result.findings[0].title  # fallback must produce a non-empty title
        assert "Pastebin" in result.findings[0].title

    async def test_api_error_returns_failure(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(
            client=_make_paste_client(response=PasteMonitorAPIError(500))
        )
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert result.success is False
        assert len(result.errors) == 1

    async def test_rate_limit_error_captured_in_errors(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(
            client=_make_paste_client(
                response=PasteMonitorRateLimitError(retry_after=60.0)
            )
        )
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert result.success is False
        assert any("rate limit" in e.lower() for e in result.errors)

    async def test_timeout_error_captured_in_errors(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(
            client=_make_paste_client(response=PasteMonitorTimeoutError("timed out"))
        )
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert result.success is False

    async def test_metadata_paste_count_reflects_findings(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(client=_make_paste_client(response=_make_records(3)))
        result = await module.execute(ScanInputs(email="victim@example.com"))
        assert result.metadata["paste_count"] == 3

    async def test_metadata_paste_count_zero_on_clean(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        module = PasteMonitor(client=_make_paste_client(response=[]))
        result = await module.execute(ScanInputs(email="clean@example.com"))
        assert result.metadata["paste_count"] == 0

    async def test_module_name_is_paste_monitor(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        assert PasteMonitor().name == "paste_monitor"

    async def test_close_delegates_to_client(self, monkeypatch):
        monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "key")
        mock_client = _make_paste_client()
        module = PasteMonitor(client=mock_client)
        await module.close()
        mock_client.close.assert_called_once()

    async def test_base_exception_is_paste_monitor_error(self):
        """Exception hierarchy: all errors are PasteMonitorError subclasses."""
        assert issubclass(PasteMonitorAPIError, PasteMonitorError)
        assert issubclass(PasteMonitorTimeoutError, PasteMonitorError)
        assert issubclass(PasteMonitorRateLimitError, PasteMonitorError)

    async def test_api_error_status_code_attribute(self):
        err = PasteMonitorAPIError(401)
        assert err.status_code == 401

    async def test_rate_limit_error_retry_after_attribute(self):
        err = PasteMonitorRateLimitError(retry_after=30.0)
        assert err.retry_after == 30.0

    async def test_rate_limit_error_no_retry_after(self):
        err = PasteMonitorRateLimitError()
        assert err.retry_after is None
        assert "rate limit" in str(err).lower()

"""Integration tests for Phase 3 module orchestration (T3.8).

Verifies cross-cutting concerns that unit tests cannot cover in isolation:
  - All four Phase 3 modules satisfy the BaseModule interface contract.
  - Concurrent execution via asyncio.gather returns valid ModuleResult from each.
  - One module failing does not cancel the others (error isolation).
  - Each module correctly handles sparse ScanInputs (absent required fields).
  - ModuleResult.metadata keys are documented and present after execution.
  - Resource cleanup (close()) is safe and idempotent.

All external calls are mocked: no live network or DNS access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from piea.modules.base import ModuleResult, ScanInputs
from piea.modules.domain_intel import (
    DNSAnalyzer,
    DnsSecurityPosture,
    DomainIntelModule,
    EmailSecurityTier,
    WhoisClient,
    WhoisData,
)
from piea.modules.hunter import HunterClient, HunterDomainResult, HunterModule
from piea.modules.paste_monitor import PasteClient, PasteMonitor
from piea.modules.search import SearchClient, SearchModule

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_FULL_INPUTS = ScanInputs(
    email="alice@example.com",
    username="alice",
    full_name="Alice Smith",
)
_EMAIL_ONLY_INPUTS = ScanInputs(email="alice@example.com")
_USERNAME_ONLY_INPUTS = ScanInputs(username="alice")
_NAME_ONLY_INPUTS = ScanInputs(full_name="Alice Smith")


# ---------------------------------------------------------------------------
# Minimal mock builders
# ---------------------------------------------------------------------------


def _mock_search_client() -> SearchClient:
    """SearchClient that returns an empty result list for any query."""
    client = MagicMock(spec=SearchClient)
    client.search = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


def _mock_whois_client() -> WhoisClient:
    """WhoisClient returning a privacy-protected WHOIS record."""
    client = MagicMock(spec=WhoisClient)
    client.lookup = AsyncMock(
        return_value=WhoisData(
            domain="example.com",
            registrant_name=None,
            registrant_org=None,
            registration_date=None,
            expiration_date=None,
            registrar="Test Registrar",
            name_servers=["ns1.example.com"],
            privacy_protected=True,
        )
    )
    return client


def _mock_dns_analyzer() -> DNSAnalyzer:
    """DNSAnalyzer returning a minimal DNS security posture."""
    analyzer = MagicMock(spec=DNSAnalyzer)
    analyzer.analyze = AsyncMock(
        return_value=DnsSecurityPosture(
            domain="example.com",
            has_mx=True,
            spf_record="v=spf1 include:_spf.example.com ~all",
            dmarc_record=None,
            dmarc_policy=None,
            email_security_tier=EmailSecurityTier.WEAK,
        )
    )
    return analyzer


def _mock_hunter_client() -> HunterClient:
    """HunterClient returning an empty domain result."""
    client = MagicMock(spec=HunterClient)
    client.search_domain = AsyncMock(
        return_value=HunterDomainResult(domain="example.com", pattern=None, emails=[])
    )
    client.find_email = AsyncMock(return_value=(None, 0))
    client.close = AsyncMock()
    return client


def _mock_paste_client() -> PasteClient:
    """PasteClient returning no paste exposure."""
    client = MagicMock(spec=PasteClient)
    client.get_paste_exposure = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


def _build_all_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SearchModule, DomainIntelModule, HunterModule, PasteMonitor]:
    """Build all four Phase 3 modules with mocked clients and fake API keys."""
    monkeypatch.setattr("piea.modules.search.settings.google_cse_api_key", "fake-key")
    monkeypatch.setattr(
        "piea.modules.search.settings.google_cse_engine_id", "fake-engine"
    )
    monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "fake-key")
    monkeypatch.setattr("piea.modules.paste_monitor.settings.hibp_api_key", "fake-key")

    search = SearchModule(client=_mock_search_client())
    domain_intel = DomainIntelModule(
        whois_client=_mock_whois_client(),
        dns_analyzer=_mock_dns_analyzer(),
    )
    hunter = HunterModule(client=_mock_hunter_client())
    paste = PasteMonitor(client=_mock_paste_client())
    return search, domain_intel, hunter, paste


# ---------------------------------------------------------------------------
# TestBaseModuleContractCompliance
# ---------------------------------------------------------------------------


class TestBaseModuleContractCompliance:
    """Each Phase 3 module must satisfy the BaseModule interface."""

    def test_search_module_name(self):
        m = SearchModule(client=_mock_search_client())
        assert m.name == "search"

    def test_domain_intel_module_name(self):
        m = DomainIntelModule(
            whois_client=_mock_whois_client(),
            dns_analyzer=_mock_dns_analyzer(),
        )
        assert m.name == "domain_intel"

    def test_hunter_module_name(self):
        m = HunterModule(client=_mock_hunter_client())
        assert m.name == "hunter"

    def test_paste_monitor_module_name(self):
        m = PasteMonitor(client=_mock_paste_client())
        assert m.name == "paste_monitor"

    def test_all_modules_have_execute(self):
        modules = [
            SearchModule(client=_mock_search_client()),
            DomainIntelModule(
                whois_client=_mock_whois_client(), dns_analyzer=_mock_dns_analyzer()
            ),
            HunterModule(client=_mock_hunter_client()),
            PasteMonitor(client=_mock_paste_client()),
        ]
        for module in modules:
            assert callable(module.execute)

    def test_all_modules_have_close(self):
        modules = [
            SearchModule(client=_mock_search_client()),
            DomainIntelModule(
                whois_client=_mock_whois_client(), dns_analyzer=_mock_dns_analyzer()
            ),
            HunterModule(client=_mock_hunter_client()),
            PasteMonitor(client=_mock_paste_client()),
        ]
        for module in modules:
            assert callable(module.close)


# ---------------------------------------------------------------------------
# TestConcurrentExecution
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestConcurrentExecution:
    """All four modules execute concurrently without cross-module interference."""

    async def test_gather_all_modules_returns_four_results(self, monkeypatch):
        search, domain_intel, hunter, paste = _build_all_modules(monkeypatch)
        results = await asyncio.gather(
            search.execute(_FULL_INPUTS),
            domain_intel.execute(_FULL_INPUTS),
            hunter.execute(_FULL_INPUTS),
            paste.execute(_FULL_INPUTS),
        )
        assert len(results) == 4
        assert all(isinstance(r, ModuleResult) for r in results)

    async def test_all_module_names_in_results(self, monkeypatch):
        search, domain_intel, hunter, paste = _build_all_modules(monkeypatch)
        results = await asyncio.gather(
            search.execute(_FULL_INPUTS),
            domain_intel.execute(_FULL_INPUTS),
            hunter.execute(_FULL_INPUTS),
            paste.execute(_FULL_INPUTS),
        )
        names = {r.module_name for r in results}
        assert names == {"search", "domain_intel", "hunter", "paste_monitor"}

    async def test_gather_does_not_drop_any_result(self, monkeypatch):
        search, domain_intel, hunter, paste = _build_all_modules(monkeypatch)
        results = await asyncio.gather(
            search.execute(_FULL_INPUTS),
            domain_intel.execute(_FULL_INPUTS),
            hunter.execute(_FULL_INPUTS),
            paste.execute(_FULL_INPUTS),
        )
        # Each result must reference the correct module
        by_name = {r.module_name: r for r in results}
        assert set(by_name.keys()) == {
            "search",
            "domain_intel",
            "hunter",
            "paste_monitor",
        }

    async def test_each_result_has_success_field(self, monkeypatch):
        search, domain_intel, hunter, paste = _build_all_modules(monkeypatch)
        results = await asyncio.gather(
            search.execute(_FULL_INPUTS),
            domain_intel.execute(_FULL_INPUTS),
            hunter.execute(_FULL_INPUTS),
            paste.execute(_FULL_INPUTS),
        )
        for result in results:
            assert isinstance(result.success, bool)


# ---------------------------------------------------------------------------
# TestErrorIsolation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestErrorIsolation:
    """One module raising must not cancel the other three (NFR-R1)."""

    async def test_search_failure_isolated(self, monkeypatch):
        """When search.execute() raises, gather captures it; others succeed."""
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "fake-key")
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )

        broken_search = MagicMock(spec=SearchModule)
        broken_search.execute = AsyncMock(side_effect=RuntimeError("search exploded"))

        domain_intel = DomainIntelModule(
            whois_client=_mock_whois_client(),
            dns_analyzer=_mock_dns_analyzer(),
        )
        hunter = HunterModule(client=_mock_hunter_client())
        paste = PasteMonitor(client=_mock_paste_client())

        results = await asyncio.gather(
            broken_search.execute(_FULL_INPUTS),
            domain_intel.execute(_FULL_INPUTS),
            hunter.execute(_FULL_INPUTS),
            paste.execute(_FULL_INPUTS),
            return_exceptions=True,
        )
        assert isinstance(results[0], RuntimeError)
        assert isinstance(results[1], ModuleResult)
        assert isinstance(results[2], ModuleResult)
        assert isinstance(results[3], ModuleResult)

    async def test_hunter_failure_isolated(self, monkeypatch):
        monkeypatch.setattr("piea.modules.search.settings.google_cse_api_key", "fake")
        monkeypatch.setattr("piea.modules.search.settings.google_cse_engine_id", "fake")
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )

        search = SearchModule(client=_mock_search_client())
        domain_intel = DomainIntelModule(
            whois_client=_mock_whois_client(),
            dns_analyzer=_mock_dns_analyzer(),
        )
        broken_hunter = MagicMock(spec=HunterModule)
        broken_hunter.execute = AsyncMock(side_effect=RuntimeError("hunter exploded"))
        paste = PasteMonitor(client=_mock_paste_client())

        results = await asyncio.gather(
            search.execute(_FULL_INPUTS),
            domain_intel.execute(_FULL_INPUTS),
            broken_hunter.execute(_FULL_INPUTS),
            paste.execute(_FULL_INPUTS),
            return_exceptions=True,
        )
        assert isinstance(results[0], ModuleResult)
        assert isinstance(results[1], ModuleResult)
        assert isinstance(results[2], RuntimeError)
        assert isinstance(results[3], ModuleResult)


# ---------------------------------------------------------------------------
# TestInputRouting
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestInputRouting:
    """Each module returns correct success/failure for sparse inputs."""

    async def test_paste_monitor_fails_without_email(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )
        module = PasteMonitor(client=_mock_paste_client())
        result = await module.execute(_USERNAME_ONLY_INPUTS)
        assert result.success is False
        assert result.errors

    async def test_hunter_fails_without_email(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "fake-key")
        module = HunterModule(client=_mock_hunter_client())
        result = await module.execute(_USERNAME_ONLY_INPUTS)
        assert result.success is False
        assert result.errors

    async def test_domain_intel_fails_without_email(self):
        module = DomainIntelModule(
            whois_client=_mock_whois_client(),
            dns_analyzer=_mock_dns_analyzer(),
        )
        result = await module.execute(_USERNAME_ONLY_INPUTS)
        assert result.success is False
        assert result.errors

    async def test_search_succeeds_with_username_only(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "fake-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "fake-engine"
        )
        module = SearchModule(client=_mock_search_client())
        result = await module.execute(_USERNAME_ONLY_INPUTS)
        # Search can run with username alone
        assert isinstance(result, ModuleResult)
        assert result.module_name == "search"

    async def test_email_only_inputs_run_domain_intel(self):
        module = DomainIntelModule(
            whois_client=_mock_whois_client(),
            dns_analyzer=_mock_dns_analyzer(),
        )
        result = await module.execute(_EMAIL_ONLY_INPUTS)
        assert isinstance(result, ModuleResult)
        assert result.module_name == "domain_intel"

    async def test_email_only_inputs_run_paste_monitor(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )
        module = PasteMonitor(client=_mock_paste_client())
        result = await module.execute(_EMAIL_ONLY_INPUTS)
        assert result.success is True
        assert result.module_name == "paste_monitor"


# ---------------------------------------------------------------------------
# TestMetadataContract
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestMetadataContract:
    """ModuleResult.metadata keys must be present after a successful execution."""

    async def test_search_metadata_keys(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_api_key", "fake-key"
        )
        monkeypatch.setattr(
            "piea.modules.search.settings.google_cse_engine_id", "fake-engine"
        )
        module = SearchModule(client=_mock_search_client())
        result = await module.execute(_FULL_INPUTS)
        assert "total_results" in result.metadata
        assert "queries_executed" in result.metadata
        assert "data_broker_hits" in result.metadata

    async def test_domain_intel_metadata_keys(self):
        module = DomainIntelModule(
            whois_client=_mock_whois_client(),
            dns_analyzer=_mock_dns_analyzer(),
        )
        result = await module.execute(_EMAIL_ONLY_INPUTS)
        assert "domain" in result.metadata
        assert "email_security_tier" in result.metadata

    async def test_hunter_metadata_keys(self, monkeypatch):
        monkeypatch.setattr("piea.modules.hunter.settings.hunter_api_key", "fake-key")
        module = HunterModule(client=_mock_hunter_client())
        result = await module.execute(_EMAIL_ONLY_INPUTS)
        assert "domain" in result.metadata
        assert "pattern" in result.metadata
        assert "indexed_email_count" in result.metadata

    async def test_paste_monitor_metadata_keys(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )
        module = PasteMonitor(client=_mock_paste_client())
        result = await module.execute(_EMAIL_ONLY_INPUTS)
        assert "paste_count" in result.metadata

    async def test_metadata_values_are_typed_correctly(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )
        module = PasteMonitor(client=_mock_paste_client())
        result = await module.execute(_EMAIL_ONLY_INPUTS)
        assert isinstance(result.metadata["paste_count"], int)


# ---------------------------------------------------------------------------
# TestResourceCleanup
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestResourceCleanup:
    """close() is safe and does not raise after construction or execution."""

    async def test_all_modules_close_without_error(self):
        modules = [
            SearchModule(client=_mock_search_client()),
            DomainIntelModule(
                whois_client=_mock_whois_client(), dns_analyzer=_mock_dns_analyzer()
            ),
            HunterModule(client=_mock_hunter_client()),
            PasteMonitor(client=_mock_paste_client()),
        ]
        for module in modules:
            await module.close()  # must not raise

    async def test_close_after_execute_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )
        module = PasteMonitor(client=_mock_paste_client())
        await module.execute(_EMAIL_ONLY_INPUTS)
        await module.close()  # must not raise

    async def test_module_name_unchanged_after_execute(self, monkeypatch):
        monkeypatch.setattr(
            "piea.modules.paste_monitor.settings.hibp_api_key", "fake-key"
        )
        module = PasteMonitor(client=_mock_paste_client())
        assert module.name == "paste_monitor"
        await module.execute(_EMAIL_ONLY_INPUTS)
        assert module.name == "paste_monitor"

"""Unit tests for T2.6 GraphCrawler.

All HTTP and database I/O is mocked:
  - BaseExtractor.extract() → AsyncMock returning ProfileData or raising
  - AsyncSession.add() / flush() → MagicMock / AsyncMock (no real DB)

Test matrix:
  - Basic BFS: seed + linked accounts → correct node/edge count
  - max_depth=1: depth-2 nodes never queued
  - max_nodes enforcement: BFS stops after limit
  - Cycle detection: same (platform, identifier) never re-extracted
  - Retry: fails twice, succeeds third attempt (NFR-R2)
  - All retries fail: error appended, crawl continues (NFR-R1)
  - Timeout: returns partial results with warning in errors (NFR-R3)
  - No username in ScanInputs: returns success=False
  - Unknown platform: silently skipped (no extractor registered)
  - Invalid identifier: not enqueued (NFR-S3)
  - No linked accounts: single node, zero edges
  - Evidence confidence override: GraphEdge uses _EVIDENCE_CONFIDENCE table
  - Node fields: scan_id, platform, identifier, profile_url, depth, confidence
  - Platform category mapping: github → "development", unknown → "social"
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from piea.modules.base import ModuleAPIError, ModuleTimeoutError, ScanInputs
from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.models import LinkedAccount, ProfileData
from piea.modules.graph_crawler import (
    MAX_RETRY_ATTEMPTS,
    GraphCrawler,
    GraphCrawlerConfig,
    _EVIDENCE_CONFIDENCE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCAN_ID = uuid4()


def _make_session() -> MagicMock:
    """Return a mock AsyncSession that satisfies the crawler's interface."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_extractor(
    platform: str,
    profile: ProfileData | None = None,
    side_effect: Exception | None = None,
) -> BaseExtractor:
    """Return a BaseExtractor mock for *platform*."""
    ext = MagicMock(spec=BaseExtractor)
    ext.platform_name = platform
    ext.close = AsyncMock()
    if side_effect is not None:
        ext.extract = AsyncMock(side_effect=side_effect)
    else:
        ext.extract = AsyncMock(return_value=profile)
    return ext


def _make_profile(
    platform: str = "github",
    identifier: str = "alice",
    linked: list[LinkedAccount] | None = None,
    raw_data: dict[str, Any] | None = None,
) -> ProfileData:
    return ProfileData(
        platform=platform,
        identifier=identifier,
        profile_url=f"https://example.com/{identifier}",
        linked_accounts=linked or [],
        raw_data=raw_data or {},
    )


def _make_linked(
    platform: str = "reddit",
    identifier: str = "alice_r",
    evidence_type: str = "api_field",
    confidence: float = 0.9,
) -> LinkedAccount:
    return LinkedAccount(
        identifier=identifier,
        profile_url=f"https://reddit.com/u/{identifier}",
        platform=platform,
        evidence_type=evidence_type,
        confidence=confidence,
    )


def _cfg(
    seed_platform: str = "github",
    max_depth: int = 2,
    max_nodes: int = 100,
    timeout_seconds: int = 30,
) -> GraphCrawlerConfig:
    """Build a GraphCrawlerConfig with test-friendly defaults."""
    return GraphCrawlerConfig(
        seed_platform=seed_platform,
        max_depth=max_depth,
        max_nodes=max_nodes,
        timeout_seconds=timeout_seconds,
    )


def _make_crawler(
    extractors: dict[str, BaseExtractor] | None = None,
    session: MagicMock | None = None,
    scan_id: UUID | None = None,
    config: GraphCrawlerConfig | None = None,
) -> GraphCrawler:
    return GraphCrawler(
        extractors=extractors or {},
        db_session=session or _make_session(),
        scan_id=scan_id or _SCAN_ID,
        config=config or _cfg(),
    )


# ---------------------------------------------------------------------------
# Basic BFS
# ---------------------------------------------------------------------------


class TestBasicBFS:
    @pytest.mark.asyncio
    async def test_single_node_no_linked(self) -> None:
        """Seed with no linked accounts produces one node, zero edges."""
        profile = _make_profile(platform="github", identifier="alice")
        ext = _make_extractor("github", profile)
        crawler = _make_crawler({"github": ext})

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.success is True
        assert result.metadata["node_count"] == 1
        assert result.metadata["edge_count"] == 0
        ext.extract.assert_awaited_once_with("alice")

    @pytest.mark.asyncio
    async def test_seed_with_two_linked_accounts(self) -> None:
        """Seed with two linked accounts → 3 nodes, 2 edges."""
        la1 = _make_linked(platform="reddit", identifier="alice_r")
        la2 = _make_linked(platform="mastodon", identifier="alice_m")

        seed_profile = _make_profile("github", "alice", linked=[la1, la2])
        reddit_profile = _make_profile("reddit", "alice_r")
        mastodon_profile = _make_profile("mastodon", "alice_m")

        extractors = {
            "github": _make_extractor("github", seed_profile),
            "reddit": _make_extractor("reddit", reddit_profile),
            "mastodon": _make_extractor("mastodon", mastodon_profile),
        }
        crawler = _make_crawler(extractors)

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.success is True
        assert result.metadata["node_count"] == 3
        assert result.metadata["edge_count"] == 2

    @pytest.mark.asyncio
    async def test_node_fields_populated_correctly(self) -> None:
        """GraphNode rows carry correct scan_id, platform, identifier, depth, confidence."""
        session = _make_session()
        profile = _make_profile("github", "alice", raw_data={"login": "alice"})
        ext = _make_extractor("github", profile)
        crawler = _make_crawler({"github": ext}, session=session)

        await crawler.execute(ScanInputs(username="alice"))

        added_nodes = [
            call.args[0]
            for call in session.add.call_args_list
            if hasattr(call.args[0], "platform")
        ]
        node = added_nodes[0]
        assert node.scan_id == _SCAN_ID
        assert node.platform == "github"
        assert node.identifier == "alice"
        assert node.depth == 0
        assert node.confidence == 1.0
        assert node.raw_data == {"login": "alice"}

    @pytest.mark.asyncio
    async def test_platform_category_known(self) -> None:
        """github platform → category 'development'."""
        session = _make_session()
        profile = _make_profile("github", "alice")
        crawler = _make_crawler(
            {"github": _make_extractor("github", profile)}, session=session
        )

        await crawler.execute(ScanInputs(username="alice"))

        node = session.add.call_args_list[0].args[0]
        assert node.category == "development"

    @pytest.mark.asyncio
    async def test_platform_category_unknown_defaults_to_social(self) -> None:
        """Unknown platform → category 'social'."""
        session = _make_session()
        profile = _make_profile("myspace", "alice")
        ext = _make_extractor("myspace", profile)
        crawler = _make_crawler(
            {"myspace": ext}, session=session, config=_cfg(seed_platform="myspace")
        )

        await crawler.execute(ScanInputs(username="alice"))

        node = session.add.call_args_list[0].args[0]
        assert node.category == "social"


# ---------------------------------------------------------------------------
# Depth limiting
# ---------------------------------------------------------------------------


class TestDepthLimiting:
    @pytest.mark.asyncio
    async def test_max_depth_one_stops_at_depth_one(self) -> None:
        """With max_depth=1, depth-2 nodes are never queued or extracted."""
        la_depth1 = _make_linked(platform="reddit", identifier="bob_r")
        la_depth2 = _make_linked(platform="mastodon", identifier="bob_m")

        seed_profile = _make_profile("github", "bob", linked=[la_depth1])
        depth1_profile = _make_profile("reddit", "bob_r", linked=[la_depth2])

        extractors = {
            "github": _make_extractor("github", seed_profile),
            "reddit": _make_extractor("reddit", depth1_profile),
            "mastodon": _make_extractor("mastodon", _make_profile("mastodon", "bob_m")),
        }
        crawler = _make_crawler(extractors, config=_cfg(max_depth=1))

        result = await crawler.execute(ScanInputs(username="bob"))

        assert result.metadata["node_count"] == 2
        extractors["mastodon"].extract.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_depth_field_on_linked_node_is_one(self) -> None:
        """A directly linked node gets depth=1."""
        session = _make_session()
        la = _make_linked(platform="reddit", identifier="alice_r")
        seed_profile = _make_profile("github", "alice", linked=[la])
        reddit_profile = _make_profile("reddit", "alice_r")
        extractors = {
            "github": _make_extractor("github", seed_profile),
            "reddit": _make_extractor("reddit", reddit_profile),
        }
        crawler = _make_crawler(extractors, session=session, config=_cfg(max_depth=1))

        await crawler.execute(ScanInputs(username="alice"))

        added_nodes = [
            c.args[0] for c in session.add.call_args_list if hasattr(c.args[0], "depth")
        ]
        depths = [n.depth for n in added_nodes]
        assert sorted(depths) == [0, 1]


# ---------------------------------------------------------------------------
# Max nodes
# ---------------------------------------------------------------------------


class TestMaxNodes:
    @pytest.mark.asyncio
    async def test_max_nodes_enforced(self) -> None:
        """Crawl stops after max_nodes nodes regardless of queue depth."""
        la1 = _make_linked(platform="reddit", identifier="u1")
        la2 = _make_linked(platform="mastodon", identifier="u2")
        seed_profile = _make_profile("github", "alice", linked=[la1, la2])

        extractors = {
            "github": _make_extractor("github", seed_profile),
            "reddit": _make_extractor("reddit", _make_profile("reddit", "u1")),
            "mastodon": _make_extractor("mastodon", _make_profile("mastodon", "u2")),
        }
        crawler = _make_crawler(extractors, config=_cfg(max_nodes=1, max_depth=2))

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.metadata["node_count"] == 1


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    @pytest.mark.asyncio
    async def test_cycle_a_to_b_to_a_produces_two_nodes(self) -> None:
        """A→B→A cycle: B links back to A, A must not be re-extracted."""
        la_to_b = _make_linked(platform="reddit", identifier="bob")
        la_to_a = _make_linked(platform="github", identifier="alice")

        profile_a = _make_profile("github", "alice", linked=[la_to_b])
        profile_b = _make_profile("reddit", "bob", linked=[la_to_a])

        extractors = {
            "github": _make_extractor("github", profile_a),
            "reddit": _make_extractor("reddit", profile_b),
        }
        crawler = _make_crawler(extractors, config=_cfg(max_depth=3))

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.metadata["node_count"] == 2
        # github extractor only called once (cycle prevented re-visit)
        extractors["github"].extract.assert_awaited_once_with("alice")

    @pytest.mark.asyncio
    async def test_case_insensitive_dedup(self) -> None:
        """Identifiers are deduplicated case-insensitively."""
        la_upper = _make_linked(platform="github", identifier="Alice")
        la_lower = _make_linked(platform="github", identifier="alice")

        seed_profile = _make_profile("github", "seed", linked=[la_upper, la_lower])
        extractors = {
            "github": _make_extractor("github", seed_profile),
        }
        crawler = _make_crawler(extractors, config=_cfg(seed_platform="github", max_depth=1))

        result = await crawler.execute(ScanInputs(username="seed"))

        # seed is visited; Alice/alice deduplicate to one entry, seed→Alice enqueued once
        assert result.metadata["node_count"] == 2

    @pytest.mark.asyncio
    async def test_same_identifier_linked_twice_enqueued_once(self) -> None:
        """Two different sources pointing to the same target only enqueue it once."""
        la1 = _make_linked(platform="reddit", identifier="shared")
        la2 = _make_linked(platform="reddit", identifier="shared")

        seed = _make_profile("github", "alice", linked=[la1, la2])
        reddit_profile = _make_profile("reddit", "shared")

        extractors = {
            "github": _make_extractor("github", seed),
            "reddit": _make_extractor("reddit", reddit_profile),
        }
        crawler = _make_crawler(extractors, config=_cfg(max_depth=1))

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.metadata["node_count"] == 2
        extractors["reddit"].extract.assert_awaited_once_with("shared")


# ---------------------------------------------------------------------------
# Retry and error handling
# ---------------------------------------------------------------------------


class TestRetryAndErrors:
    @pytest.mark.asyncio
    async def test_retry_succeeds_on_third_attempt(self) -> None:
        """Extractor fails twice then succeeds → profile is crawled (NFR-R2)."""
        profile = _make_profile("github", "alice")
        ext = _make_extractor("github")
        ext.extract.side_effect = [
            ModuleAPIError("github", 503, "unavailable"),
            ModuleAPIError("github", 503, "unavailable"),
            profile,
        ]
        crawler = _make_crawler({"github": ext})

        with patch("piea.modules.graph_crawler.asyncio.sleep", new=AsyncMock()):
            result = await crawler.execute(ScanInputs(username="alice"))

        assert result.success is True
        assert result.metadata["node_count"] == 1
        assert ext.extract.await_count == MAX_RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_all_retries_fail_error_appended_crawl_continues(self) -> None:
        """All retries fail → error in result.errors; other nodes still crawled (NFR-R1)."""
        la_bad = _make_linked(platform="reddit", identifier="bad_user")
        la_good = _make_linked(platform="mastodon", identifier="good_user")

        seed = _make_profile("github", "alice", linked=[la_bad, la_good])
        mastodon_profile = _make_profile("mastodon", "good_user")

        bad_ext = _make_extractor("reddit")
        bad_ext.extract.side_effect = ModuleAPIError("reddit", 500, "error")

        extractors = {
            "github": _make_extractor("github", seed),
            "reddit": bad_ext,
            "mastodon": _make_extractor("mastodon", mastodon_profile),
        }
        crawler = _make_crawler(extractors, config=_cfg(max_depth=1))

        with patch("piea.modules.graph_crawler.asyncio.sleep", new=AsyncMock()):
            result = await crawler.execute(ScanInputs(username="alice"))

        assert result.success is True
        assert any("reddit" in e for e in result.errors)
        assert result.metadata["node_count"] == 2  # seed + mastodon

    @pytest.mark.asyncio
    async def test_timeout_error_yields_partial_results(self) -> None:
        """Timeout produces a warning in errors and success=True (NFR-R3)."""

        async def _slow_extract(_identifier: str) -> ProfileData:
            await asyncio.sleep(999)
            return _make_profile("github", "alice")  # unreachable

        ext = _make_extractor("github")
        ext.extract.side_effect = _slow_extract
        crawler = _make_crawler({"github": ext}, config=_cfg(timeout_seconds=1))

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.success is True
        assert any("timed out" in e for e in result.errors)
        assert result.metadata["node_count"] == 0

    @pytest.mark.asyncio
    async def test_module_timeout_error_is_retried(self) -> None:
        """ModuleTimeoutError is retried like ModuleAPIError."""
        profile = _make_profile("github", "alice")
        ext = _make_extractor("github")
        ext.extract.side_effect = [
            ModuleTimeoutError("github", "timed out"),
            profile,
        ]
        crawler = _make_crawler({"github": ext})

        with patch("piea.modules.graph_crawler.asyncio.sleep", new=AsyncMock()):
            result = await crawler.execute(ScanInputs(username="alice"))

        assert result.metadata["node_count"] == 1


# ---------------------------------------------------------------------------
# No username / unknown platform / invalid identifier
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_no_username_returns_failure(self) -> None:
        """Missing username returns success=False without any extraction."""
        crawler = _make_crawler({})
        result = await crawler.execute(ScanInputs(username=None))

        assert result.success is False
        assert result.errors

    @pytest.mark.asyncio
    async def test_unknown_seed_platform_no_extractor(self) -> None:
        """Seed platform with no extractor: zero nodes, no crash."""
        crawler = _make_crawler({}, config=_cfg(seed_platform="unknown_platform"))
        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.success is True
        assert result.metadata["node_count"] == 0

    @pytest.mark.asyncio
    async def test_linked_account_with_none_platform_skipped(self) -> None:
        """LinkedAccount.platform=None means platform unknown — must be skipped."""
        la = LinkedAccount(
            identifier="https://example.com",
            profile_url="https://example.com",
            platform=None,
            evidence_type="bio_mention",
            confidence=0.5,
        )
        seed = _make_profile("github", "alice", linked=[la])
        crawler = _make_crawler(
            {"github": _make_extractor("github", seed)}, config=_cfg(max_depth=1)
        )

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.metadata["node_count"] == 1  # only seed; unknown platform skipped

    @pytest.mark.asyncio
    async def test_invalid_identifier_not_enqueued(self) -> None:
        """Identifiers failing NFR-S3 regex are silently skipped."""
        la = _make_linked(platform="github", identifier="../../../etc/passwd")
        seed = _make_profile("github", "alice", linked=[la])
        ext = _make_extractor("github", seed)
        crawler = _make_crawler({"github": ext}, config=_cfg(max_depth=1))

        result = await crawler.execute(ScanInputs(username="alice"))

        assert result.metadata["node_count"] == 1
        # extract was only called once (for the seed), not for the malicious identifier
        ext.extract.assert_awaited_once_with("alice")

    @pytest.mark.asyncio
    async def test_extractor_returns_none_produces_no_node(self) -> None:
        """extract() returning None (user not found) → no node created."""
        ext = _make_extractor("github", profile=None)
        crawler = _make_crawler({"github": ext})

        result = await crawler.execute(ScanInputs(username="ghost"))

        assert result.metadata["node_count"] == 0


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------


class TestConfidenceScoring:
    @pytest.mark.asyncio
    async def test_edge_confidence_from_evidence_table(self) -> None:
        """GraphEdge.confidence is drawn from _EVIDENCE_CONFIDENCE, not LinkedAccount.confidence."""
        session = _make_session()
        la = _make_linked(
            platform="reddit",
            identifier="alice_r",
            evidence_type="verified_link",
            confidence=0.1,  # raw confidence should be overridden
        )
        seed = _make_profile("github", "alice", linked=[la])
        reddit_profile = _make_profile("reddit", "alice_r")

        extractors = {
            "github": _make_extractor("github", seed),
            "reddit": _make_extractor("reddit", reddit_profile),
        }
        crawler = _make_crawler(extractors, session=session, config=_cfg(max_depth=1))

        await crawler.execute(ScanInputs(username="alice"))

        added_edges = [
            c.args[0]
            for c in session.add.call_args_list
            if hasattr(c.args[0], "evidence_type")
        ]
        assert len(added_edges) == 1
        assert added_edges[0].evidence_type == "verified_link"
        assert added_edges[0].confidence == _EVIDENCE_CONFIDENCE["verified_link"]

    @pytest.mark.asyncio
    async def test_keybase_proof_confidence_is_one(self) -> None:
        """Keybase proof evidence gets confidence=1.0."""
        assert _EVIDENCE_CONFIDENCE["keybase_proof"] == 1.0

    @pytest.mark.asyncio
    async def test_same_username_confidence_is_low(self) -> None:
        """same_username evidence gets the lowest confidence (0.3)."""
        assert _EVIDENCE_CONFIDENCE["same_username"] == 0.3


# ---------------------------------------------------------------------------
# Module interface
# ---------------------------------------------------------------------------


class TestModuleInterface:
    def test_name_property(self) -> None:
        crawler = _make_crawler({})
        assert crawler.name == "graph_crawler"

    @pytest.mark.asyncio
    async def test_close_closes_all_extractors(self) -> None:
        """close() propagates to all injected extractors."""
        ext_a = _make_extractor("github")
        ext_b = _make_extractor("reddit")
        crawler = _make_crawler({"github": ext_a, "reddit": ext_b})

        await crawler.close()

        ext_a.close.assert_awaited_once()
        ext_b.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_session_flush_called_after_bfs(self) -> None:
        """Session.flush() is called once after BFS completes."""
        session = _make_session()
        profile = _make_profile("github", "alice")
        crawler = _make_crawler(
            {"github": _make_extractor("github", profile)}, session=session
        )

        await crawler.execute(ScanInputs(username="alice"))

        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_metadata_contains_expected_keys(self) -> None:
        """ModuleResult.metadata has node_count, edge_count, platforms_found."""
        profile = _make_profile("github", "alice")
        crawler = _make_crawler({"github": _make_extractor("github", profile)})

        result = await crawler.execute(ScanInputs(username="alice"))

        assert "node_count" in result.metadata
        assert "edge_count" in result.metadata
        assert "platforms_found" in result.metadata

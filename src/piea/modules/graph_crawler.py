"""Graph crawler — BFS identity-graph expansion with database persistence.

T2.6 implementation. Entry point: GraphCrawler.execute(ScanInputs).

Design:
  - Seed: inputs.username crawled on seed_platform (default "github")
  - BFS via asyncio.Queue; entries carry (identifier, platform, depth,
    confidence, parent_node_id | None, linked_account | None)
  - Visited deduplication: set keyed on (platform.lower(), identifier.lower())
  - Concurrency cap: asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)
  - Timeout: asyncio.wait_for wraps the entire BFS loop
  - Retry: up to MAX_RETRY_ATTEMPTS with exponential back-off (L009-safe)
  - Persistence: GraphNode + GraphEdge rows via injected AsyncSession

FR-4.3 confidence scoring:
  evidence_type      confidence
  keybase_proof      1.0
  verified_link      1.0
  api_field          0.9
  bio_mention        0.7
  same_username      0.3
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from piea.config import settings
from piea.db.models import GraphEdge, GraphNode
from piea.modules.base import (
    BaseModule,
    ModuleAPIError,
    ModuleResult,
    ModuleTimeoutError,
    ScanInputs,
)
from piea.modules.extractors.base import BaseExtractor
from piea.modules.extractors.models import LinkedAccount, ProfileData

logger = logging.getLogger(__name__)

MAX_CONCURRENT_EXTRACTIONS = 5
MAX_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0  # seconds; doubles each attempt

# FR-4.3 confidence table keyed by evidence_type string
_EVIDENCE_CONFIDENCE: dict[str, float] = {
    "keybase_proof": 1.0,
    "verified_link": 1.0,
    "api_field": 0.9,
    "bio_mention": 0.7,
    "same_username": 0.3,
}

# Platform name → GraphNode.category
_PLATFORM_CATEGORY: dict[str, str] = {
    "github": "development",
    "gitlab": "development",
    "keybase": "security",
    "reddit": "social_media",
    "mastodon": "social_media",
    "gravatar": "identity",
    "twitter": "social_media",
    "linkedin": "professional",
}

# NFR-S3: identifier validation before URL substitution.
# No slashes or colons — prevents path traversal in constructed URLs.
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9._@\-]{1,500}$")

# BFS queue entry type alias
_QueueEntry = tuple[str, str, int, float, UUID | None, LinkedAccount | None]


@dataclass
class _BFSState:
    """Mutable state threaded through the BFS crawl loop."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    queue: asyncio.Queue[_QueueEntry] = field(default_factory=asyncio.Queue)


@dataclass(frozen=True, slots=True)
class GraphCrawlerConfig:
    """Configuration for a single GraphCrawler run.

    Attributes:
        seed_platform: Platform to start the BFS from. Default "github".
        max_depth: Maximum link traversal depth. Defaults to settings value.
        max_nodes: Maximum nodes to persist. Defaults to settings value.
        timeout_seconds: Wall-clock timeout. Defaults to settings value.
    """

    seed_platform: str = "github"
    max_depth: int | None = None
    max_nodes: int | None = None
    timeout_seconds: int | None = None


class GraphCrawler(BaseModule):
    """BFS identity-graph crawler that persists GraphNode/GraphEdge rows.

    Args:
        extractors: Mapping of platform name → BaseExtractor instance.
            The crawler only visits platforms that have a registered extractor.
        db_session: Async SQLAlchemy session; caller owns the transaction.
        scan_id: UUID of the Scan record this crawl belongs to.
        config: Optional run configuration. Defaults applied from settings.
    """

    def __init__(
        self,
        extractors: dict[str, BaseExtractor],
        db_session: AsyncSession,
        scan_id: UUID,
        config: GraphCrawlerConfig | None = None,
    ) -> None:
        cfg = config or GraphCrawlerConfig()
        self._extractors = extractors
        self._session = db_session
        self._scan_id = scan_id
        self._seed_platform = cfg.seed_platform
        self._max_depth = (
            cfg.max_depth if cfg.max_depth is not None else settings.scan_max_depth
        )
        self._max_nodes = (
            cfg.max_nodes if cfg.max_nodes is not None else settings.scan_max_nodes
        )
        self._timeout = (
            cfg.timeout_seconds
            if cfg.timeout_seconds is not None
            else settings.scan_timeout_seconds
        )
        self._visited: set[tuple[str, str]] = set()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)

    @property
    def name(self) -> str:
        return "graph_crawler"

    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Run BFS from inputs.username on seed_platform.

        Returns ModuleResult with success=True even on partial results.
        A timeout produces a warning in errors, not a failure (NFR-R3).
        """
        if not inputs.username:
            return ModuleResult(
                module_name=self.name,
                success=False,
                errors=["No username provided in scan inputs"],
            )

        state = _BFSState()
        try:
            state = await asyncio.wait_for(
                self._run_bfs(inputs.username),
                timeout=float(self._timeout),
            )
        except TimeoutError:
            state.errors.append(
                f"Crawl timed out after {self._timeout}s — returning partial results"
            )

        metadata: dict[str, Any] = {
            "node_count": len(state.nodes),
            "edge_count": len(state.edges),
            "platforms_found": list({n.platform for n in state.nodes}),
        }
        return ModuleResult(
            module_name=self.name,
            success=True,
            errors=state.errors,
            metadata=metadata,
        )

    async def close(self) -> None:
        """Close all injected extractors."""
        for extractor in self._extractors.values():
            await extractor.close()

    # ------------------------------------------------------------------
    # BFS core
    # ------------------------------------------------------------------

    async def _run_bfs(self, seed_identifier: str) -> _BFSState:
        """Execute BFS from seed_identifier; returns completed state."""
        state = _BFSState()
        state.queue.put_nowait(
            (seed_identifier, self._seed_platform, 0, 1.0, None, None)
        )
        self._mark_visited(self._seed_platform, seed_identifier)

        while not state.queue.empty() and len(state.nodes) < self._max_nodes:
            entry = await state.queue.get()
            await self._process_queue_entry(entry, state)

        await self._session.flush()
        return state

    async def _process_queue_entry(self, entry: _QueueEntry, state: _BFSState) -> None:
        """Extract one BFS queue entry and append results to state."""
        identifier, platform, depth, confidence, parent_id, linked = entry
        extractor = self._extractors.get(platform)
        if extractor is None:
            return

        profile = await self._extract_with_retry(extractor, identifier, state.errors)
        if profile is None:
            return

        node = await self._persist_node(profile, depth, confidence)
        state.nodes.append(node)

        if linked is not None and parent_id is not None:
            edge = await self._persist_edge(parent_id, node, linked)
            state.edges.append(edge)

        if depth < self._max_depth:
            self._enqueue_linked(profile, node.id, depth, state.queue)

    def _enqueue_linked(
        self,
        profile: ProfileData,
        parent_id: UUID,
        depth: int,
        queue: asyncio.Queue[_QueueEntry],
    ) -> None:
        """Add unvisited linked accounts from profile to the BFS queue."""
        for la in profile.linked_accounts:
            if not la.platform:
                continue
            if not self._validate_identifier(la.identifier):
                logger.debug(
                    "Skipping invalid identifier %r from %s", la.identifier, la.platform
                )
                continue
            if self._is_visited(la.platform, la.identifier):
                continue
            self._mark_visited(la.platform, la.identifier)
            node_confidence = _EVIDENCE_CONFIDENCE.get(la.evidence_type, la.confidence)
            queue.put_nowait(
                (la.identifier, la.platform, depth + 1, node_confidence, parent_id, la)
            )

    # ------------------------------------------------------------------
    # Extraction with retry
    # ------------------------------------------------------------------

    async def _extract_with_retry(
        self,
        extractor: BaseExtractor,
        identifier: str,
        errors: list[str],
    ) -> ProfileData | None:
        """Call extractor.extract() with up to MAX_RETRY_ATTEMPTS retries.

        Semaphore limits concurrent in-flight extractor calls (L009-safe:
        sleep is outside the semaphore context so it is never held during wait).
        """
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                async with self._semaphore:
                    return await extractor.extract(identifier)
            except (ModuleAPIError, ModuleTimeoutError) as exc:
                if attempt == MAX_RETRY_ATTEMPTS - 1:
                    errors.append(
                        f"{extractor.platform_name}: {exc}"
                    )  # no identifier — L007
                    return None
                await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))
        return None  # unreachable; satisfies mypy

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def _persist_node(
        self,
        profile: ProfileData,
        depth: int,
        confidence: float,
    ) -> GraphNode:
        """Create a GraphNode row and stage it in the session."""
        category = _PLATFORM_CATEGORY.get(profile.platform.lower(), "social")
        node = GraphNode(
            id=uuid4(),  # set explicitly so node.id is usable before flush
            scan_id=self._scan_id,
            platform=profile.platform,
            identifier=profile.identifier,
            profile_url=profile.profile_url,
            confidence=confidence,
            depth=depth,
            category=category,
            raw_data=profile.raw_data,
        )
        self._session.add(node)
        return node

    async def _persist_edge(
        self,
        source_id: UUID,
        target_node: GraphNode,
        linked: LinkedAccount,
    ) -> GraphEdge:
        """Create a GraphEdge row and stage it in the session."""
        confidence = _EVIDENCE_CONFIDENCE.get(linked.evidence_type, linked.confidence)
        edge = GraphEdge(
            id=uuid4(),
            scan_id=self._scan_id,
            source_node_id=source_id,
            target_node_id=target_node.id,
            evidence_type=linked.evidence_type,
            confidence=confidence,
        )
        self._session.add(edge)
        return edge

    # ------------------------------------------------------------------
    # Cycle detection + identifier validation
    # ------------------------------------------------------------------

    def _is_visited(self, platform: str, identifier: str) -> bool:
        return (platform.lower(), identifier.lower()) in self._visited

    def _mark_visited(self, platform: str, identifier: str) -> None:
        self._visited.add((platform.lower(), identifier.lower()))

    def _validate_identifier(self, identifier: str) -> bool:
        """Return True if identifier is safe for URL substitution (NFR-S3)."""
        return bool(_IDENTIFIER_RE.match(identifier))

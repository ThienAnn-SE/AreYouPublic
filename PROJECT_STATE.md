# PROJECT_STATE.md — Living Project Context (Self-Managed by Claude Code)

**Purpose:** This file is Claude Code's persistent memory. It prevents hallucination, context drift, and contradictory decisions across tasks. Claude Code must read this file before starting any task and update it after completing any task.

**Last updated:** 2026-03-22 — Phase 3 Task T3.1 Search Engine Enumeration (COMPLETE)
**Updated by:** Claude Code
**Current phase:** Phase 3 — Search & domain intelligence (T3.1 COMPLETE → T3.2 next)
**Repository:** https://github.com/ThienAnn-SE/AreYouPublic (public)

---

## 1. Project identity

| Field | Value |
|-------|-------|
| Project name | Public Information Exposure Analyzer (PIEA) |
| Type | Web-based security assessment tool |
| Purpose | Aggregate publicly available information about an individual, build recursive identity graph, compute risk score, deliver exposure report |
| Primary language | Python 3.11+ |
| Frontend | React 18 + TypeScript |
| Backend framework | FastAPI |
| Database | PostgreSQL 16 |
| Cache/Broker | Redis 7 |
| Task queue | Celery 5.3 |
| Deployment | Docker Compose |
| Repository | https://github.com/ThienAnn-SE/AreYouPublic |
| Default branch | master |
| CI/CD | GitHub Actions (lint, type-check, test, security scan) |
| Branch protection | master — requires CI Pass + Security Pass status checks |
| Security workflow | SECURITY_WORKFLOW.md — 4 gates: pre-commit, CI, review, runtime |
| Reference documents | PROJECT_PLAN.md, SRS.md, CODING_RULES.md, SECURITY_WORKFLOW.md |

---

## 2. Project file hierarchy

**Update this section after EVERY task. This must reflect the actual files on disk at all times.**

```
piea/
├── .gitignore                          [Status: created — GitHub setup]
├── .env.example                        [Status: created — GitHub setup]
├── .pre-commit-config.yaml             [Status: created — Security setup]
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                      [Status: created — GitHub setup, updated — Security setup]
│   │   └── security.yml                [Status: created — Security setup]
│   └── pull_request_template.md        [Status: created — GitHub setup]
├── SECURITY_WORKFLOW.md                [Status: created — Security setup]
├── docker-compose.yml                  [Status: created — T0.2]
├── Dockerfile                          [Status: created — T0.2]
├── pyproject.toml                      [Status: created — T0.1, updated — GitHub setup]
├── alembic.ini                         [Status: created — T0.3]
├── LICENSE                             [Status: created — GitHub setup]
├── README.md                           [Status: created — GitHub setup]
├── PROGRESS.md                         [Status: not created]
├── INSTALL_LOG.md                      [Status: not created]
├── PROJECT_STATE.md                    [Status: THIS FILE]
├── PROJECT_PLAN.md                     [Status: reference doc]
├── SRS.md                              [Status: reference doc]
├── CODING_RULES.md                     [Status: reference doc]
├── CLAUDE_CODE_PROMPT.md               [Status: reference doc]
├── LEGAL.md                            [Status: created — T0.7]
├── alembic/
│   ├── env.py                          [Status: created — T0.3]
│   └── versions/
│       └── 001_initial_schema.py       [Status: created — T0.3]
├── src/
│   └── piea/
│       ├── __init__.py                 [Status: created — T0.3]
│       ├── main.py                     [Status: created — T0.5]
│       ├── config.py                   [Status: created — T0.5]
│       ├── api/
│       │   ├── __init__.py             [Status: created — T0.5]
│       │   ├── routes/
│       │   │   ├── scans.py            [Status: created — T0.5]
│       │   │   ├── reports.py          [Status: created — T0.5, scaffold]
│       │   │   └── health.py           [Status: created — T0.5]
│       │   ├── schemas/
│       │   │   ├── scan_request.py     [Status: created — T0.5, needs model_validator]
│       │   │   ├── scan_response.py    [Status: created — T0.5]
│       │   │   └── report.py           [Status: not created — T5.4]
│       │   └── dependencies.py         [Status: created — T0.5]
│       ├── core/
│       │   ├── __init__.py             [Status: created — T0.4]
│       │   ├── consent.py              [Status: created — T0.4]
│       │   ├── orchestrator.py         [Status: not created]
│       │   ├── rate_limiter.py         [Status: not created]
│       │   ├── cache.py                [Status: created — T1.4]
│       │   └── audit.py                [Status: not created]
│       ├── modules/
│       │   ├── __init__.py             [Status: created — T1.1]
│       │   ├── base.py                 [Status: created — T1.1]
│       │   ├── hibp.py                 [Status: created — T1.1/T1.2/T1.3/T1.4/T1.6]
│       │   ├── username/
│       │   │   ├── __init__.py         [Status: created — T2.1]
│       │   │   ├── platforms.py        [Status: created — T2.1]
│       │   │   ├── checker.py          [Status: created — T2.2]
│       │   │   ├── rate_limiter.py     [Status: created — T2.3]
│       │   │   └── module.py           [Status: created — T2.4]
│       │   ├── graph_crawler.py        [Status: created — T2.6]
│       │   ├── search.py              [Status: created — T3.1]
│       │   ├── domain_intel.py         [Status: not created]
│       │   ├── paste_monitor.py        [Status: not created]
│       │   └── extractors/
│       │       ├── __init__.py         [Status: created — T2.5]
│       │       ├── models.py           [Status: created — T2.5]
│       │       ├── base.py             [Status: created — T2.5]
│       │       ├── bio_parser.py       [Status: created — T2.5]
│       │       ├── github.py           [Status: created — T2.5]
│       │       ├── mastodon.py         [Status: created — T2.5]
│       │       ├── keybase.py          [Status: created — T2.5]
│       │       ├── gitlab.py           [Status: created — T2.5]
│       │       ├── gravatar.py         [Status: created — T2.5]
│       │       └── reddit.py           [Status: created — T2.5]
│       ├── scoring/
│       │   ├── __init__.py             [Status: not created]
│       │   ├── risk_scorer.py          [Status: not created]
│       │   ├── tier_classifier.py      [Status: not created]
│       │   ├── remediation.py          [Status: not created]
│       │   └── taxonomy.py             [Status: not created]
│       ├── graph/
│       │   ├── __init__.py             [Status: not created]
│       │   ├── models.py              [Status: not created]
│       │   └── serializer.py          [Status: not created]
│       ├── db/
│       │   ├── __init__.py             [Status: created — T0.3]
│       │   ├── models.py              [Status: created — T0.3]
│       │   ├── session.py             [Status: created — T0.3]
│       │   └── repositories/
│       │       ├── scan_repo.py        [Status: not created]
│       │       └── audit_repo.py       [Status: not created]
│       └── tasks/
│           ├── __init__.py             [Status: not created]
│           └── scan_task.py            [Status: not created]
├── config/
│   ├── platforms.json                  [Status: created — T2.1]
│   ├── data_brokers.json               [Status: created — T3.1]
│   └── risk_taxonomy.json              [Status: not created]
├── frontend/                           [Status: not created — Phase 6]
├── tests/
│   ├── __init__.py                     [Status: created — T0.6]
│   ├── conftest.py                     [Status: created — T0.6]
│   ├── fixtures/                       [Status: created — T0.6, empty]
│   ├── unit/
│   │   ├── __init__.py                 [Status: created — T0.6]
│   │   ├── test_health.py             [Status: created — T0.6]
│   │   ├── test_consent.py            [Status: created — T0.6]
│   │   ├── test_scan_request.py       [Status: created — T0.6]
│   │   ├── test_hibp.py              [Status: created — T1.5]
│   │   ├── test_username_platforms.py [Status: created — T2.1]
│   │   ├── test_username_rate_limiter.py [Status: created — T2.3]
│   │   ├── test_username_checker.py  [Status: created — T2.2]
│   │   ├── test_username_module.py   [Status: created — T2.4]
│   │   ├── test_extractors.py        [Status: created — T2.5]
│   │   ├── test_graph_crawler.py      [Status: created — T2.6]
│   │   └── test_search.py             [Status: created — T3.1]
│   └── integration/
│       └── __init__.py                 [Status: created — T0.6]
└── docs/                               [Status: not created — Phase 7]
```

**File count:** 70 created / ~65 planned
**Last hierarchy update:** 2026-03-21

---

## 3. Implementation status

### 3.1 Phase completion tracker

| Phase | Name | Status | Tasks done | Tasks total | Milestone verified |
|-------|------|--------|-----------|------------|-------------------|
| 0 | Project setup & ethics | COMPLETE | 7 | 7 | No — pending `docker compose up` verification |
| 1 | Breach exposure module | COMPLETE | 6 | 6 | No — pending integration test with real HIBP API key |
| 2 | Username enum & graph crawler | COMPLETE | 6 | 14 | No — all Phase 2 tasks complete |
| 3 | Search & domain intelligence | IN PROGRESS | 1 | 8 | No — T3.1 complete, T3.2 next |
| 4 | Risk scoring engine | NOT STARTED | 0 | 7 | No |
| 5 | Scan orchestration & API | NOT STARTED | 0 | 7 | No |
| 6 | Frontend & report UI | NOT STARTED | 0 | 12 | No |
| 7 | Hardening & documentation | NOT STARTED | 0 | 8 | No |

### 3.2 Current task queue

```
COMPLETE:   T2.1 — Build platform registry (62 sites, 13 categories, JSON config)
COMPLETE:   T2.2 — Implement async username checker with httpx pooling, semaphore(50)
COMPLETE:   T2.3 — Build per-platform rate limiter (token bucket, exponential backoff, Redis fallback)
COMPLETE:   T2.4 — Implement UsernameModule (BaseModule interface, batch result aggregation)
COMPLETE:   T2.5 — Platform-specific extractors (9 files, bio parser, 47 tests, 166 total)
COMPLETE:   T2.6 — Graph crawler implementation (BFS with rate limiting, 27 tests, 90% coverage)
COMPLETE:   T3.1 — Search engine enumeration module (SearchModule, 22 broker config, 22 tests, 91% coverage)
NEXT UP:    T3.2 — ResultCategorizer class (categorizes search results)
```

### 3.3 Completed tasks log

| Task ID | Description | Completed | Files created/modified |
|---------|------------|-----------|----------------------|
| T0.1 | Initialize Python project with pyproject.toml, ruff, mypy config | 2026-03-21 | pyproject.toml |
| T0.2 | Set up Docker Compose (PostgreSQL, Redis, FastAPI) | 2026-03-21 | docker-compose.yml, Dockerfile |
| T0.3 | Create database schema and Alembic migrations | 2026-03-21 | alembic.ini, alembic/env.py, alembic/versions/001_initial_schema.py, src/piea/__init__.py, src/piea/db/__init__.py, src/piea/db/models.py, src/piea/db/session.py |
| T0.4 | Implement consent gate module | 2026-03-21 | src/piea/core/__init__.py, src/piea/core/consent.py |
| T0.5 | Build API scaffolding | 2026-03-21 | src/piea/config.py, src/piea/main.py, src/piea/db/session.py (updated), src/piea/api/__init__.py, src/piea/api/dependencies.py, src/piea/api/routes/__init__.py, src/piea/api/routes/health.py, src/piea/api/routes/scans.py, src/piea/api/routes/reports.py, src/piea/api/schemas/__init__.py, src/piea/api/schemas/scan_request.py, src/piea/api/schemas/scan_response.py |
| T0.6 | Set up pytest fixtures and test infrastructure | 2026-03-21 | pyproject.toml (updated), tests/__init__.py, tests/conftest.py, tests/unit/__init__.py, tests/unit/test_health.py, tests/unit/test_consent.py, tests/unit/test_scan_request.py, tests/integration/__init__.py |
| T0.7 | Write LEGAL.md with terms of use and disclaimer | 2026-03-21 | LEGAL.md |
| GitHub | Initialize git repo, create GitHub repository, CI/CD, branch protection | 2026-03-21 | .gitignore, .env.example, .github/workflows/ci.yml, .github/pull_request_template.md, README.md, LICENSE, pyproject.toml (updated URLs) |
| Security | Security workflow with 4 gates, secret scanning CI, pre-commit hooks, PROCESS.md Phase 5S | 2026-03-21 | SECURITY_WORKFLOW.md, .github/workflows/security.yml, .pre-commit-config.yaml, .gitignore (updated), PROCESS.md (updated — Phase 5S added), .github/workflows/ci.yml (updated — master branch) |
| T1.1 | Implement HIBP API v3 client with API key auth, rate limiting, retry with exponential backoff | 2026-03-21 | src/piea/modules/__init__.py, src/piea/modules/base.py, src/piea/modules/hibp.py |
| T1.2 | Build breach data parser and severity classifier (Critical/High/Medium/Low based on data classes) | 2026-03-21 | src/piea/modules/hibp.py (classify_breach_severity, BreachRecord) |
| T1.3 | Implement password hash check using k-anonymity range endpoint | 2026-03-21 | src/piea/modules/hibp.py (HIBPClient.check_password_hash) |
| T1.4 | Add response caching with Redis (24h TTL, SHA-256 keyed) | 2026-03-21 | src/piea/core/cache.py, src/piea/modules/hibp.py (cache integration), src/piea/api/dependencies.py (updated) |
| T1.5 | Write 31 unit tests with mocked API responses (respx) | 2026-03-21 | tests/unit/test_hibp.py |
| T1.6 | Build breach findings data model (BreachRecord, BaseModule, ModuleFinding, ModuleResult) | 2026-03-21 | src/piea/modules/base.py |
| T2.1 | Build platform registry with 62 sites (13 categories, JSON config with URL patterns, fixtures) | 2026-03-21 | config/platforms.json, src/piea/modules/username/platforms.py, tests/unit/test_username_platforms.py |
| T2.2 | Implement async username checker with httpx connection pooling, SSRF prevention, Semaphore(50) | 2026-03-21 | src/piea/modules/username/checker.py, tests/unit/test_username_checker.py |
| T2.3 | Build token bucket rate limiter with exponential backoff, 429 handling, Redis fallback | 2026-03-21 | src/piea/modules/username/rate_limiter.py, tests/unit/test_username_rate_limiter.py |
| T2.4 | Implement UsernameModule (BaseModule interface, batch result aggregation, error handling) | 2026-03-21 | src/piea/modules/username/module.py, tests/unit/test_username_module.py, src/piea/modules/username/__init__.py |
| T2.5 | Implement platform-specific profile extractors (9 modules, bio parser, 47 tests) | 2026-03-21 | src/piea/modules/extractors/__init__.py, models.py, base.py, bio_parser.py, github.py, mastodon.py, keybase.py, gitlab.py, gravatar.py, reddit.py, tests/unit/test_extractors.py |
| T2.6 | Implement graph crawler with BFS, rate limiting, SQLAlchemy persistence (27 tests, 90% coverage) | 2026-03-21 | src/piea/modules/graph_crawler.py, tests/unit/test_graph_crawler.py |
| T3.1 | Implement search engine enumeration module (Google CSE, dynamic queries, broker detection, 22 tests) | 2026-03-22 | src/piea/modules/search.py, config/data_brokers.json, tests/unit/test_search.py |

---

## 4. Established interfaces and contracts

**CRITICAL: Once an interface is established and other code depends on it, it must not change without updating ALL dependents. Track every interface here.**

### 4.1 Base module interface

```
Status: CREATED (Task T1.1)
File: src/piea/modules/base.py

Contract:
  class BaseModule(ABC):
    @property name -> str                      # unique module identifier
    async execute(inputs: ScanInputs) -> ModuleResult   # main scan logic
    async close() -> None                       # resource cleanup

  ScanInputs(frozen dataclass):
    - email: str | None
    - username: str | None
    - full_name: str | None

  ModuleResult(frozen dataclass):
    - module_name: str
    - success: bool
    - findings: list[ModuleFinding]
    - errors: list[str]
    - cached: bool
    - metadata: dict[str, object]

  ModuleFinding(frozen dataclass):
    - finding_type: str
    - severity: Severity (StrEnum: critical/high/medium/low/info)
    - category: str
    - title: str
    - description: str
    - platform: str | None
    - evidence: dict[str, object]
    - remediation_action: str
    - remediation_effort: str
    - remediation_url: str | None
    - weight: float

Implemented by: HIBPModule (src/piea/modules/hibp.py)
```

### 4.2 Data models registry

**Track every dataclass and Pydantic model here once created. Include the exact field names and types so future tasks reference the real implementation, not the SRS specification.**

```
MODEL: BreachRecord (frozen dataclass, slots=True)
FILE: src/piea/modules/hibp.py
CREATED AT: Task T1.6
FIELDS:
  - name: str
  - title: str
  - domain: str
  - breach_date: str
  - added_date: str
  - pwn_count: int
  - description: str
  - data_classes: list[str]
  - is_verified: bool = False
  - is_sensitive: bool = False
  - severity: Severity = Severity.LOW
USED BY: hibp.py (HIBPClient, HIBPModule)

MODEL: Severity (StrEnum)
FILE: src/piea/modules/base.py
CREATED AT: Task T1.6
VALUES: critical, high, medium, low, info
USED BY: hibp.py, base.py (ModuleFinding)

MODEL: PlatformCheckResult (frozen dataclass)
FILE: src/piea/modules/username/checker.py
CREATED AT: Task T2.2
FIELDS:
  - platform: str
  - url: str
  - category: str
  - status: CheckStatus enum (FOUND, NOT_FOUND, ERROR, RATE_LIMITED)
  - checked_at: datetime
  - error_message: str | None
USED BY: UsernameChecker.check_all_platforms(), UsernameModule.execute()

MODEL: CheckStatus (StrEnum)
FILE: src/piea/modules/username/checker.py
CREATED AT: Task T2.2
VALUES: found, not_found, error, rate_limited
USED BY: PlatformCheckResult, UsernameChecker

MODEL: Platform (frozen dataclass)
FILE: src/piea/modules/username/platforms.py
CREATED AT: Task T2.1
FIELDS:
  - name: str
  - url_pattern: str
  - category: str
  - request_timeout: float
  - http_method: str (default: get)
USED BY: PlatformRegistry, UsernameChecker

MODEL: ProfileData (frozen dataclass)
FILE: src/piea/modules/extractors/models.py
CREATED AT: Task T2.5
FIELDS:
  - platform: str
  - identifier: str
  - profile_url: str
  - display_name: str | None
  - bio: str | None
  - location: str | None
  - emails: list[str]
  - linked_accounts: list[LinkedAccount]
  - raw_data: dict[str, Any]
USED BY: BaseExtractor.extract(), graph crawler (T2.6)

MODEL: LinkedAccount (frozen dataclass)
FILE: src/piea/modules/extractors/models.py
CREATED AT: Task T2.5
FIELDS:
  - identifier: str
  - profile_url: str
  - platform: str
  - evidence_type: str (values: "api_field" | "verified_link" | "bio_mention" | "keybase_proof")
  - confidence: float
USED BY: ProfileData.linked_accounts, graph crawler (T2.6)

MODEL: BioToken (frozen dataclass)
FILE: src/piea/modules/extractors/models.py
CREATED AT: Task T2.5
FIELDS:
  - token_type: str (url, email, mastodon_handle, bare_handle)
  - raw_value: str
  - normalized_value: str
  - platform: str
  - confidence: float
USED BY: BioParser.parse(), extractor implementations
```

### 4.3 Username module public interfaces

```
Status: CREATED (Task T2.2-T2.4)
File: src/piea/modules/username/checker.py, module.py

Interface: UsernameChecker
  async check_all_platforms(username: str) -> list[PlatformCheckResult]
  async check_platform(platform: Platform, username: str) -> PlatformCheckResult
  async close() -> None

Interface: RateLimiterFactory
  @staticmethod get(platform: str, rpm: int) -> TokenBucketRateLimiter

Interface: TokenBucketRateLimiter
  async acquire() -> None
  record_429(retry_after: float) -> None

Interface: UsernameModule (implements BaseModule)
  name -> "username"
  async execute(inputs: ScanInputs) -> ModuleResult
    - Calls check_all_platforms(inputs.username)
    - Aggregates results into ModuleResult with findings
    - Handles errors with graceful fallback

Implementation notes:
  - SSRF prevention: username regex validated before URL construction
  - Rate limiting: Semaphore(50) for concurrent requests + per-platform token bucket
  - Redis fallback: In-process dict if Redis unavailable
  - Result aggregation: _aggregate_results() keeps execute() under 20 lines
```

### 4.3a Profile extractor interfaces

```
Status: CREATED (Task T2.5)
File: src/piea/modules/extractors/

Model: ProfileData (frozen dataclass)
  - platform: str
  - identifier: str
  - profile_url: str
  - display_name: str | None
  - bio: str | None
  - location: str | None
  - emails: list[str]
  - linked_accounts: list[LinkedAccount]
  - raw_data: dict[str, Any]

Model: LinkedAccount (frozen dataclass)
  - identifier: str
  - profile_url: str
  - platform: str
  - evidence_type: str (values: "api_field" | "verified_link" | "bio_mention" | "keybase_proof")
  - confidence: float (0.0 to 1.0)

Model: BioToken (frozen dataclass)
  - token_type: str (url, email, mastodon_handle, bare_handle)
  - raw_value: str
  - normalized_value: str
  - platform: str
  - confidence: float (0.0 to 1.0)

Interface: BaseExtractor (ABC)
  async extract(identifier: str) -> ProfileData | None
  _safe_get(key: str, default: Any) -> Any  [helper complying with L007]

Interface: BioParser
  parse(text: str) -> list[BioToken]
    Uses span tracking to avoid overlapping token extraction

Implemented extractors:
  - GitHubExtractor (api.github.com/users/{username})
  - MastodonExtractor (multi-instance fallback, verified links confidence=1.0)
  - KeybaseExtractor (cryptographic proof extraction, confidence=1.0)
  - GitLabExtractor (gitlab.com/api/v4/users)
  - GravatarExtractor (MD5(email) identifier, email never transmitted)
  - RedditExtractor (PIEA User-Agent, 403=suspended=None)

Dependencies:
  - All extractors comply with L007: httpx.HTTPStatusError caught and re-raised as ModuleAPIError
  - BioParser uses regex with overlap-aware span tracking
  - LinkedIn account detection via verified links (confidence=1.0) per Mastodon API response
```

### 4.3b Graph crawler interface

```
Status: CREATED (Task T2.6)
File: src/piea/modules/graph_crawler.py

Configuration: GraphCrawlerConfig (frozen dataclass)
  - seed_platform: str (e.g., "twitter", "github", "mastodon")
  - max_depth: int (default: 3, limits BFS traversal)
  - max_nodes: int (default: 500, limits graph size)
  - timeout_seconds: float (default: 300.0, total BFS time limit)

State: _BFSState (dataclass, mutable)
  - nodes: list[GraphNode] — discovered nodes
  - edges: list[GraphEdge] — discovered edges
  - errors: list[str] — error messages
  - queue: asyncio.Queue[(identifier, depth, parent_id)]

Interface: GraphCrawler (implements BaseModule)
  name -> "graph_crawler"
  async execute(inputs: ScanInputs, config: GraphCrawlerConfig) -> ModuleResult
    - Calls _run_bfs(seed_identifier) with async queue
    - Persists all discovered nodes and edges to database
    - Returns ModuleResult with findings + metadata

  Private methods:
  - async _run_bfs(seed_identifier: str) -> _BFSState
    BFS using asyncio.Queue, respects max_depth and max_nodes
    visited set keyed on (platform.lower(), identifier.lower())
    asyncio.wait_for wraps entire BFS for timeout protection

  - async _process_queue_entry(entry, state) -> None
    Dequeues one (identifier, depth, parent_id) triple
    Extracts profile via platform extractor
    Enqueues discovered linked accounts if depth < max_depth

  - async _extract_with_retry(extractor, identifier, errors) -> ProfileData | None
    Calls extractor.extract(identifier) with MAX_RETRY_ATTEMPTS=3
    Exponential backoff: 2^attempt seconds
    Catches and logs errors; no re-raise

  - async _persist_node(profile: ProfileData, depth: int, confidence: float) -> GraphNode
    Creates SQLAlchemy GraphNode with id=uuid4() set explicitly
    Fields: platform, identifier, profile_url, depth, confidence, raw_data
    Returns persisted node for use in edge creation

  - async _persist_edge(source_id: UUID, target_node: GraphNode, linked: LinkedAccount) -> GraphEdge
    Creates SQLAlchemy GraphEdge with explicit id=uuid4()
    confidence taken from LinkedAccount.confidence
    evidence_type from LinkedAccount.evidence_type

  - async _enqueue_linked(profile: ProfileData, parent_id: UUID, depth: int, queue)
    Iterates profile.linked_accounts
    Validates identifier against _IDENTIFIER_RE = r"^[a-zA-Z0-9._@\-]{1,500}$"
    Enqueues if (platform, identifier) not visited and depth < max_depth

Key design notes:
  - BFS via asyncio.Queue; no max-connections semaphore (extractors have rate limits)
  - Visited set keyed on (platform.lower(), identifier.lower()) for case-insensitive dedup
  - asyncio.wait_for wraps entire _run_bfs() — timeout protection (NFR-R3)
  - GraphNode.id and GraphEdge.id set explicitly at construction (L012 pattern)
  - Error messages exclude identifiers — no PII leaking (L007 compliance)
  - _IDENTIFIER_RE validates no slashes/colons in identifiers (NFR-S3)
```

### 4.3c Search module interface

```
Status: CREATED (Task T3.1)
File: src/piea/modules/search.py

Configuration: SearchModuleConfig (frozen dataclass)
  - api_key: str (Google Custom Search API key)
  - search_engine_id: str (Google Custom Search Engine ID)
  - max_queries: int (default: 3, limits query variations per search)

Data: SearchClient (httpx-based)
  async search(query: str) -> dict[str, Any] | None
    Makes paginated Google Custom Search JSON API requests
    Catches httpx.HTTPStatusError and re-raises as ModuleAPIError (L007)
    Returns None on 429 (partial findings ok per design)

Interface: SearchModule (implements BaseModule)
  name -> "search"
  async execute(inputs: ScanInputs) -> ModuleResult
    - If no email: return early (email-only module)
    - Constructs up to 3 search queries (username@*, username site:data-broker, etc.)
    - Calls search() for each query
    - Detects data broker domains in results using domain matching
    - Aggregates into ModuleFinding per broker discovered

Broker detection:
  - display_link normalized: .lower().removeprefix("www.")
  - Extract last 2 labels (domain.tld) via rsplit(".", 1)
  - Match against 22 broker domains from config/data_brokers.json

Data models:
  - SearchResult (frozen dataclass): title, link, display_link, snippet
  - SearchAPIResponse (frozen dataclass): items, queries
  - Evidence dict typed dict[str, Any] per L003 (not object)

Key design notes:
  - SearchModuleConfig dataclass groups 4 init params → single-param rule
  - Rate-limit (429) returns success=False with partial findings, not exception
  - Broker domain matching uses removeprefix (not lstrip) per L012 learning
  - Test paths anchored with Path(__file__).parents[2] / "config" per L012
```

### 4.4 API endpoint registry

**Track every FastAPI endpoint once created. Future tasks must match these exact paths and schemas.**

```
Status: NO ENDPOINTS CREATED YET

When endpoints are created, log them here:

ENDPOINT: POST /api/v1/scans
FILE: src/piea/api/routes/scans.py
CREATED AT: Task T5.4
REQUEST MODEL: ScanRequest (from api/schemas/scan_request.py)
RESPONSE MODEL: ScanResponse (from api/schemas/scan_response.py)
STATUS CODE: 201
```

### 4.5 Database table registry

**Track every SQLAlchemy model and its actual column names once created.**

```
Status: TABLES CREATED (Task T0.3)

When tables are created, log them here:

TABLE: consent_records
FILE: src/piea/db/models.py
CREATED AT: Task T0.3
COLUMNS:
  - id: UUID (PK)
  - attestation_type: VARCHAR(50)
  - operator_name: VARCHAR(255)
  - operator_ip: INET
  - consent_text_version: VARCHAR(20)
  - created_at: TIMESTAMPTZ
RELATIONSHIPS:
  - scans → ConsentRecord (one-to-many)

TABLE: scans
FILE: src/piea/db/models.py
CREATED AT: Task T0.3
COLUMNS:
  - id: UUID (PK)
  - consent_record_id: UUID (FK → consent_records.id)
  - status: VARCHAR(20)
  - input_name_hash: VARCHAR(64)
  - input_email_hash: VARCHAR(64)
  - input_username: VARCHAR(255)
  - risk_score: INTEGER
  - risk_tier: VARCHAR(20)
  - modules_config: JSONB
  - started_at: TIMESTAMPTZ
  - completed_at: TIMESTAMPTZ
  - error_message: TEXT
  - created_at: TIMESTAMPTZ
RELATIONSHIPS:
  - consent_record → ConsentRecord (many-to-one)
  - findings → list[Finding] (one-to-many, cascade delete)
  - graph_nodes → list[GraphNode] (one-to-many, cascade delete)
  - graph_edges → list[GraphEdge] (one-to-many, cascade delete)
  - audit_logs → list[AuditLog] (one-to-many, cascade delete)

TABLE: findings
FILE: src/piea/db/models.py
CREATED AT: Task T0.3
COLUMNS:
  - id: UUID (PK)
  - scan_id: UUID (FK → scans.id)
  - type: VARCHAR(100)
  - severity: VARCHAR(20)
  - category: VARCHAR(50)
  - title: VARCHAR(500)
  - description: TEXT
  - platform: VARCHAR(100)
  - evidence: JSONB
  - weight_applied: FLOAT
  - remediation_action: TEXT
  - remediation_effort: VARCHAR(20)
  - remediation_url: VARCHAR(500)
RELATIONSHIPS:
  - scan → Scan (many-to-one)

TABLE: graph_nodes
FILE: src/piea/db/models.py
CREATED AT: Task T0.3
COLUMNS:
  - id: UUID (PK)
  - scan_id: UUID (FK → scans.id)
  - platform: VARCHAR(100)
  - identifier: VARCHAR(500)
  - profile_url: VARCHAR(1000)
  - confidence: FLOAT
  - depth: INTEGER
  - category: VARCHAR(50)
  - raw_data: JSONB
RELATIONSHIPS:
  - scan → Scan (many-to-one)
  - outgoing_edges → list[GraphEdge] (one-to-many)
  - incoming_edges → list[GraphEdge] (one-to-many)

TABLE: graph_edges
FILE: src/piea/db/models.py
CREATED AT: Task T0.3
COLUMNS:
  - id: UUID (PK)
  - scan_id: UUID (FK → scans.id)
  - source_node_id: UUID (FK → graph_nodes.id)
  - target_node_id: UUID (FK → graph_nodes.id)
  - evidence_type: VARCHAR(50)
  - confidence: FLOAT
RELATIONSHIPS:
  - scan → Scan (many-to-one)
  - source_node → GraphNode (many-to-one)
  - target_node → GraphNode (many-to-one)

TABLE: audit_logs
FILE: src/piea/db/models.py
CREATED AT: Task T0.3
COLUMNS:
  - id: UUID (PK)
  - scan_id: UUID (FK → scans.id)
  - event_type: VARCHAR(50)
  - event_data: JSONB
  - operator_ip: INET
  - created_at: TIMESTAMPTZ
RELATIONSHIPS:
  - scan → Scan (many-to-one)
```

### 4.6 Exception hierarchy

**Track every custom exception class to prevent duplicate definitions or conflicting hierarchies.**

```
Status: NOT YET CREATED

Planned hierarchy (update with actual once created):

PIEAError (base)
├── APIError (base for HTTP-facing errors)
│   ├── ScanNotFoundError
│   ├── ConsentRequiredError
│   └── RateLimitError
├── ModuleError (base for data source failures)
│   ├── HIBPError
│   │   └── HIBPRateLimitError
│   ├── PlatformError
│   │   ├── PlatformNotFoundError
│   │   ├── PlatformTimeoutError
│   │   └── PlatformAPIError
│   └── GraphCrawlerError
│       ├── MaxDepthReachedError
│       └── CrawlTimeoutError
└── ScoringError
```

---

## 5. Key decisions log

**Every non-trivial technical decision gets logged here. This prevents Claude Code from re-deciding differently in a later task.**

| ID | Decision | Reason | Made at task | Affects |
|----|---------|--------|-------------|---------|
| D1 | (example) Use asyncpg not psycopg3 | Required by SQLAlchemy async engine on PostgreSQL | PROJECT_PLAN.md | db/session.py |
| D2 | (example) Use respx not aioresponses for HTTP mocking | Better httpx integration, maintained | PROJECT_PLAN.md | All test files |
| D3 | Strict consent version enforcement — any version mismatch rejects the record | Operator chose option A; maximises legal clarity over UX convenience | T0.4 | core/consent.py, future API |
| D4 | ConsentService uses db.flush() not db.commit() — caller owns the transaction | Correct pattern for services nested in FastAPI dependency-injected sessions | T0.4 | core/consent.py, api/dependencies.py |
| D5 | LEGAL.md is the canonical source for consent text and report disclaimer | Single source of truth; consent.py version constant must stay in sync | T0.7 | LEGAL.md, core/consent.py, future report generator |
| D6 | Use GitHub Actions for CI/CD, not external CI services | Integrated with GitHub, free for public repos, native PR checks | GitHub setup | .github/workflows/ci.yml |
| D7 | Branch protection on master requires "CI Pass" status check | Prevents merging broken code; CI Pass is a composite job that gates on lint+typecheck+test | GitHub setup | GitHub repo settings |
| D8 | Default branch is master (not main) | User preference | GitHub setup | All git workflows |
| D9 | Security verification (Phase 5S) is mandatory between implementation and testing | Prevents secrets/PII from reaching CI logs or git history; defense in depth | Security setup | PROCESS.md, SECURITY_WORKFLOW.md |
| D10 | Branch protection requires both CI Pass AND Security Pass | Two independent gate jobs ensure code quality and security are verified separately | Security setup | GitHub repo settings |
| D11 | Test data must use RFC 2606/5737 synthetic identifiers only | Prevents accidental PII in public git history and CI logs | Security setup | SECURITY_WORKFLOW.md Section 5 |
| D12 | PII must be hashed or redacted in log statements at INFO level or below | Prevents PII exposure via log aggregators; aligns with GDPR data minimization | Security setup | SECURITY_WORKFLOW.md Section 3.4 |

---

## 6. Dependency and import map

**Track what imports what to prevent circular dependencies. Update after every task.**

```
Status: NOT YET CREATED

When modules exist, map them here:

src/piea/config.py
  ← imported by: main.py, api/dependencies.py, tasks/scan_task.py
  → imports: pydantic_settings

src/piea/modules/base.py
  ← imported by: all module implementations, orchestrator.py
  → imports: (stdlib only)

src/piea/modules/hibp.py
  ← imported by: orchestrator.py, tests/unit/test_hibp.py
  → imports: modules/base.py, core/cache.py, httpx

(etc.)
```

**Circular dependency rule:** If adding an import would create a cycle, STOP and restructure. Never use lazy imports to work around cycles.

---

## 7. Environment state

| Item | Status | Version | Notes |
|------|--------|---------|-------|
| Git | INSTALLED | — | Repository initialized |
| GitHub CLI (gh) | INSTALLED | 2.88.1 | Authenticated as ThienAnn-SE |
| GitHub repo | CREATED | — | https://github.com/ThienAnn-SE/AreYouPublic (public) |
| GitHub Actions CI | CONFIGURED | — | Runs on PR to master and push to master |
| GitHub Actions Security | CONFIGURED | — | Secret scan, PII scan, dependency audit, file classification |
| Branch protection | CONFIGURED | — | master requires CI Pass + Security Pass |
| Pre-commit hooks | CONFIGURED | — | detect-secrets, private-key detection, PII patterns |
| Python | NOT VERIFIED | — | Required: 3.11+ |
| Node.js | NOT VERIFIED | — | Required: 20+ |
| Docker | NOT VERIFIED | — | Required: 24+ |
| Docker Compose | NOT VERIFIED | — | Required: v2 |
| Virtual env | NOT CREATED | — | Path: .venv |
| PostgreSQL container | NOT RUNNING | — | Port: 5432 |
| Redis container | NOT RUNNING | — | Port: 6379 |
| pip packages | NOT INSTALLED | — | See PROJECT_PLAN.md §11 |
| npm packages | NOT INSTALLED | — | Phase 6 only |

---

## 8. Configuration values in use

**Track the actual configuration values and environment variables that have been coded into the Settings class. This prevents later tasks from using different variable names.**

```
Status: Settings class NOT YET CREATED (Task T0.1)

When created, log every setting here:

ENV VAR: HIBP_API_KEY
PYTHON FIELD: hibp_api_key
TYPE: str
DEFAULT: (none — required)
USED IN: modules/hibp.py

ENV VAR: SCAN_MAX_DEPTH
PYTHON FIELD: scan_max_depth
TYPE: int
DEFAULT: 3
USED IN: modules/graph_crawler.py, api/schemas/scan_request.py
```

---

## 9. Test fixtures registry

**Track every test fixture file to prevent duplication and ensure consistency.**

```
Status: NO FIXTURES CREATED YET

When fixtures are created:

FIXTURE: tests/fixtures/hibp_breach_response.json
CREATED AT: Task T1.5
DESCRIBES: HIBP API v3 response for email with 3 breaches
USED BY: tests/unit/test_hibp.py
CONTAINS: Array of 3 breach objects (LinkedIn, Adobe, Canva)

FIXTURE: tests/fixtures/github_profile_testuser.json
CREATED AT: Task T2.14
DESCRIBES: GitHub API response for a user with linked accounts
USED BY: tests/unit/test_github_extractor.py, tests/unit/test_graph_crawler.py
CONTAINS: Profile with bio, blog, twitter_username, company fields populated
```

---

## 10. Active risks and blockers

| ID | Type | Description | Status | Affects task |
|----|------|------------|--------|-------------|
| R001 | INFO | Coverage threshold is currently 50%. Must be raised as each new module gets tests. Current modules tested: HIBP (87%). | OPEN | T2.x, T3.x, T4.x |
| R002 | INFO | conftest.py uses SQLite for local dev with type overrides for INET/JSONB. Any new PostgreSQL-specific ORM type must also be registered in `_register_sqlite_type_overrides()`. | OPEN | T2.x, T3.x |
| R003 | INFO | Redis cache stores breach data as plaintext JSON. Per SECURITY_WORKFLOW.md §3.4 threat T8, at-rest encryption is deferred to a future task. | OPEN | Future |

**Risk types:** BLOCKER (cannot proceed), WARNING (can proceed with caution), INFO (noted for future reference)

---

## 11. Naming conventions in use

**Track the actual names used in the codebase to enforce consistency. Once a name is used, all future references must use the same name.**

### Class names

| Class | File | Purpose |
|-------|------|---------|
| Base | src/piea/db/models.py | SQLAlchemy declarative base |
| ConsentRecord | src/piea/db/models.py | Consent audit record |
| Scan | src/piea/db/models.py | Scan entity |
| Finding | src/piea/db/models.py | Risk finding |
| GraphNode | src/piea/db/models.py | Identity graph node |
| GraphEdge | src/piea/db/models.py | Identity graph edge |
| AuditLog | src/piea/db/models.py | Audit log entry |
| ConsentInput | src/piea/core/consent.py | Pydantic model for consent form submission |
| ConsentService | src/piea/core/consent.py | Service: create/validate/retrieve consent records |
| ConsentError | src/piea/core/consent.py | Base exception for consent failures |
| ConsentValidationError | src/piea/core/consent.py | Field-level validation failure |
| ConsentRequiredError | src/piea/core/consent.py | Scan attempted without valid consent |
| BaseExtractor | src/piea/modules/extractors/base.py | Abstract base for platform profile extractors |
| BioParser | src/piea/modules/extractors/bio_parser.py | Regex-based bio text parser with overlap awareness |
| GitHubExtractor | src/piea/modules/extractors/github.py | Profile extractor for GitHub API |
| MastodonExtractor | src/piea/modules/extractors/mastodon.py | Profile extractor for Mastodon with multi-instance support |
| KeybaseExtractor | src/piea/modules/extractors/keybase.py | Cryptographic proof extractor for Keybase |
| GitLabExtractor | src/piea/modules/extractors/gitlab.py | Profile extractor for GitLab API |
| GravatarExtractor | src/piea/modules/extractors/gravatar.py | Avatar service profile extractor (MD5-based) |
| RedditExtractor | src/piea/modules/extractors/reddit.py | Profile extractor for Reddit with User-Agent |

### Function names (public API)

| Function | File | Purpose |
|----------|------|---------|
| (none yet) | | |

### Pydantic model names

| Model | File | Purpose | Direction |
|-------|------|---------|-----------|
| (none yet) | | | request/response/internal |

### Table names

| Table | ORM class | File |
|-------|----------|------|
| (none yet) | | |

---

## 12. Cross-task dependency notes

**Some tasks depend on specific implementation details from earlier tasks. Log those dependencies here so later tasks don't contradict earlier work.**

```
Example format:

T2.12 (graph crawler) DEPENDS ON:
  - T2.11: IdentityGraph class must have .add_node() and .add_edge() methods
  - T2.10: BioLinkParser must return list[tuple[str, str]] as (platform, identifier)
  - T2.3: RateLimiter must expose async context manager interface

T4.2 (risk scorer) DEPENDS ON:
  - T4.1: risk_taxonomy.json must be loaded and validated at startup
  - T2.11: IdentityGraph must expose .node_count and .edge_count properties
  - T1.6: BreachFinding must have .severity and .data_classes fields
```

T2.6 (graph crawler) DEPENDS ON:
  - T2.5: BaseExtractor.extract() returns ProfileData with linked_accounts
  - T2.5: ProfileData.linked_accounts must contain (identifier, platform, profile_url, confidence, evidence_type)
  - T2.5: BioParser.parse() returns list[BioToken] with token_type and normalized_value for link extraction
  - T2.1: Platform registry must be available for profile URL validation
  - T2.2: UsernameChecker must remain available for recursive checking during graph traversal

---

## 13. Self-check questions

**Before starting ANY task, Claude Code must answer these questions by checking this file:**

1. What phase am I in? (Section 3.1)
2. What task am I about to start? (Section 3.2)
3. What files already exist that I might need to import from? (Section 2)
4. What interfaces/contracts are already established that I must conform to? (Section 4)
5. What class names, function names, and model names are already in use? (Section 11)
6. Are there any decisions I should not re-make? (Section 5)
7. Are there any cross-task dependencies I need to respect? (Section 12)
8. Are there any active blockers? (Section 10)

**If any answer is unclear or this file seems out of date, run the verification commands and update it before proceeding.**

---

## UPDATE INSTRUCTIONS

**After completing every task, Claude Code must update the following sections:**

1. `Last updated` timestamp at the top of this file
2. `Current phase` at the top of this file
3. Section 2: Change file status from `not created` to `created — T[X.Y]` for every file created or modified
4. Section 3.1: Update task counts and phase status
5. Section 3.2: Advance the task queue
6. Section 3.3: Add the completed task to the log
7. Section 4: Add any new interfaces, models, endpoints, tables, or exceptions
8. Section 5: Add any new technical decisions
9. Section 6: Update the import map for new files
10. Section 8: Add any new configuration values
11. Section 9: Add any new test fixtures
12. Section 11: Add any new class names, function names, or model names
13. Section 12: Add any cross-task dependencies discovered

**If a section has no changes, leave it as-is. Never delete previous entries — this is an append-only log.**
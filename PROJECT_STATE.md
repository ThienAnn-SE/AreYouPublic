# PROJECT_STATE.md — Living Project Context (Self-Managed by Claude Code)

**Purpose:** This file is Claude Code's persistent memory. It prevents hallucination, context drift, and contradictory decisions across tasks. Claude Code must read this file before starting any task and update it after completing any task.

**Last updated:** 2026-03-22 — Phase 3 Task T3.8 Integration tests (COMPLETE)
**Updated by:** Claude Code
**Current phase:** Phase 3 COMPLETE (T3.1 ✓, T3.2 ✓, T3.3 ✓, T3.6 ✓, T3.7 ✓, T3.8 ✓ → Phase 4 next)
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
│       │   ├── __init__.py             [Status: created — T1.1, updated — T3.1]
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
│       │   ├── domain_intel.py         [Status: created — T3.2]
│       │   ├── hunter.py               [Status: created — T3.6]
│       │   ├── paste_monitor.py        [Status: created — T3.7]
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
│   │   ├── test_search.py             [Status: created — T3.1]
│   │   ├── test_domain_intel.py        [Status: created — T3.2]
│   │   ├── test_hunter.py             [Status: created — T3.6]
│   │   └── test_paste_monitor.py      [Status: created — T3.7]
│   └── integration/
│       ├── __init__.py                 [Status: created — T0.6]
│       └── test_phase3_modules.py      [Status: created — T3.8]
└── docs/                               [Status: not created — Phase 7]
```

**File count:** 75 created / ~65 planned (hunter.py, test_hunter.py, paste_monitor.py, test_paste_monitor.py, test_phase3_modules.py added; pyproject.toml updated)
**Last hierarchy update:** 2026-03-22

---

## 3. Implementation status

### 3.1 Phase completion tracker

| Phase | Name | Status | Tasks done | Tasks total | Milestone verified |
|-------|------|--------|-----------|------------|-------------------|
| 0 | Project setup & ethics | COMPLETE | 7 | 7 | No — pending `docker compose up` verification |
| 1 | Breach exposure module | COMPLETE | 6 | 6 | No — pending integration test with real HIBP API key |
| 2 | Username enum & graph crawler | COMPLETE | 6 | 14 | No — all Phase 2 tasks complete, awaiting Phase 3 |
| 3 | Search & domain intelligence | COMPLETE | 8 | 8 | No — All Phase 3 tasks complete, ready for Phase 4 |
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
COMPLETE:   T3.1 — Search engine enumeration module (SearchModule, 6 result categories, DataBrokerDetector, 50 tests, 93% coverage)
COMPLETE:   T3.2 — Domain intelligence module (WhoisClient + DNSAnalyzer, ~750 lines, 71 tests, 90% coverage)
COMPLETE:   T3.3 — EntityResolver (name collision handling via secondary signals, 5 test classes, 95% coverage for search.py)
COMPLETE:   T3.6 — Hunter.io email pattern lookup (HunterClient, 3 findings types, 97% coverage, L007 + L009 compliant)
COMPLETE:   T3.7 — Paste site monitor (PasteMonitor, HIBP paste-account API, 100% coverage, 1 HIGH-severity finding per paste, L007 + L009 compliant)
COMPLETE:   T3.8 — Integration tests for Phase 3 modules (test_phase3_modules.py, 6 test classes, 30+ integration tests, 91.69% coverage, all 456 tests passing)
NEXT UP:    T4.1 — Risk scoring engine foundation (score computation, weighting, severity classification)
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
| T3.1 | Implement search engine enumeration module (Google CSE, 6 result categories, 24-domain data broker detector, 50 tests, 93% coverage) | 2026-03-21 | src/piea/modules/search.py, tests/unit/test_search.py, src/piea/modules/__init__.py (updated) |
| T3.2 | Implement domain intelligence module (WhoisClient, DNSAnalyzer, EmailSecurityTier enum, privacy heuristic, SPF/DMARC detection, 71 tests, 90% coverage) | 2026-03-22 | src/piea/modules/domain_intel.py, tests/unit/test_domain_intel.py, src/piea/modules/__init__.py (updated), pyproject.toml (mypy override for whois) |
| T3.3 | Implement EntityResolver for name collision handling via secondary signals (DisambiguationResult, common names heuristic, COMMON_NAME_RESULT_THRESHOLD constant, 5 test classes, 95% coverage) | 2026-03-22 | src/piea/modules/search.py (enhanced), tests/unit/test_search.py (enhanced), src/piea/modules/__init__.py (updated) |
| T3.6 | Implement HunterClient for Hunter.io email pattern lookup (domain-search + email-finder, partial success logic, 3 finding types, 97% coverage, rate-limit + API error handling per L007/L009) | 2026-03-22 | src/piea/modules/hunter.py, tests/unit/test_hunter.py, src/piea/modules/__init__.py (updated), pyproject.toml (hunter package + mypy override) |
| T3.7 | Implement PasteMonitor for HIBP paste-account exposure (PasteClient + PasteMonitor, 1 HIGH finding per paste, 100% coverage, rate-limit + PII protection per L007/L009) | 2026-03-22 | src/piea/modules/paste_monitor.py, tests/unit/test_paste_monitor.py, src/piea/modules/__init__.py (updated) |
| T3.8 | Integration tests for Phase 3 modules (contract compliance, concurrent execution, error isolation, input routing, metadata validation, resource cleanup) | 2026-03-22 | tests/integration/test_phase3_modules.py (473 lines, 6 test classes, 30+ tests, 91.69% project coverage) |

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

MODEL: SearchResult (frozen dataclass)
FILE: src/piea/modules/search.py
CREATED AT: Task T3.1
FIELDS:
  - title: str
  - url: str
  - snippet: str
  - category: str (values: personal_site, social_profile, data_broker, credential_leak, news_mention, other)
  - confidence: float (0.0 to 1.0)
USED BY: SearchModule.execute(), ResultCategorizer.categorize(), EntityResolver.filter_results()

MODEL: DisambiguationResult (frozen dataclass, slots=True)
FILE: src/piea/modules/search.py
CREATED AT: Task T3.3
FIELDS:
  - matched_results: list[SearchResult]
  - is_common_name: bool
  - has_secondary_signals: bool
  - filtered_count: int
USED BY: SearchModule._aggregate_results() for name collision disambiguation
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

### 4.3c Search engine enumeration module

```
Status: CREATED (Task T3.1)
File: src/piea/modules/search.py

Configuration: SearchModuleConfig (frozen dataclass)
  - api_key: str (Google Custom Search API key — required)
  - search_engine_id: str (Google Custom Search engine ID — required)
  - queries_per_input: int (default: 3, max queries to construct from input)
  - max_results_per_query: int (default: 10, Google CSE limit)
  - timeout_seconds: float (default: 30.0, per request timeout)

Data model: SearchResult (frozen dataclass)
  - title: str
  - url: str
  - snippet: str
  - category: str (values: personal_site, social_profile, data_broker, credential_leak, news_mention, other)
  - confidence: float (0.0 to 1.0)

Data model: SearchQueryBatch
  - Contains up to 3 queries constructed from email/username/full_name
  - Queries designed to avoid overlapping results

Interface: SearchModule (implements BaseModule)
  name -> "search"
  async execute(inputs: ScanInputs, config: SearchModuleConfig) -> ModuleResult
    - Calls _build_queries(inputs) to construct 1–3 search queries
    - Calls _search_all_queries() to execute batched Google CSE API requests
    - Calls ResultCategorizer.categorize() to classify each result
    - Calls DataBrokerDetector.check() to identify data broker domains
    - Aggregates findings (FOUND findings for results, EXPOSED findings for data brokers)
    - Returns ModuleResult with findings + metadata

  Private methods:
  - _build_queries(inputs: ScanInputs) -> list[str]
    Constructs 1–3 queries to avoid duplicates:
    - Q1: email or username (whichever is primary input)
    - Q2: full_name with secondary identifier
    - Q3: secondary identifiers in combination
    Returns list with 0–3 unique queries

  - async _search_all_queries(queries: list[str], config) -> list[SearchResult]
    Batches queries into single Google CSE API call (supports max 10 queries per call)
    Parses search results, applies rate-limit handling
    Returns flattened list of SearchResult objects

  - async _search_google(query: str, config) -> list[SearchResult]
    Low-level Google CSE API client
    Handles 403 quota errors with SearchQuotaError
    Rate-limits via asyncio.sleep() after request

Interface: ResultCategorizer
  CATEGORY_PATTERNS = {
    "personal_site": [r"(portfolio|blog|website|mysite)"],
    "social_profile": [r"(github|twitter|linkedin|reddit|mastodon|keybase)"],
    "data_broker": [domain list — see DataBrokerDetector],
    "credential_leak": [r"(pastebin|paste\.org|hastebin)"],
    "news_mention": [r"(news|article|press)"],
    "other": [catch-all]
  }
  categorize(result: SearchResult) -> SearchResult (with category set)

Interface: DataBrokerDetector
  BROKER_DOMAINS = {
    whitepages.com, spokeo.com, intelius.com, ... [24 domains total]
  }
  OPT_OUT_URLS = {
    whitepages.com: "https://www.whitepages.com/privacy",
    ... [10 opt-out URLs]
  }
  check(url: str) -> (bool, str | None)
    Returns (is_data_broker: bool, opt_out_url: str | None)

Exception hierarchy:
  SearchModuleError (base)
  SearchAPIError (Google CSE API error)
  SearchQuotaError (403 quota exceeded)

Key design notes:
  - Query construction avoids duplicates by tracking primary_type (email/username)
  - Rate-limiting uses asyncio.sleep() after Google CSE requests
  - ResultCategorizer uses regex patterns for domain-based categorization
  - DataBrokerDetector maintains opt-out URL registry for remediation
  - Error messages exclude search terms — no PII leaking (L007 compliance)

### 4.3d Domain intelligence module (Task T3.2)

```
Status: CREATED (Task T3.2)
File: src/piea/modules/domain_intel.py

Constants:
  - WHOIS_TIMEOUT_SECONDS: float = 30.0
  - _PRIVACY_KEYWORDS: frozenset[str] (privacy, proxy, whoisguard, redacted, hidden, protected)

Exceptions:
  - DomainIntelError (base — domain error)
  - DomainIntelTimeoutError (extends DomainIntelError)
  - DomainIntelLookupError (extends DomainIntelError)
  - DomainIntelRateLimitError (extends DomainIntelError)

Data models:
  - WhoisData (frozen dataclass, slots=True)
    - domain: str
    - registrant_name: str | None
    - registrant_org: str | None
    - creation_date: datetime | None
    - expiration_date: datetime | None
    - updated_date: datetime | None
    - nameservers: list[str]
    - privacy_protected: bool

  - DnsSecurityPosture (frozen dataclass, slots=True)
    - domain: str
    - has_spf: bool
    - spf_record: str | None
    - has_dmarc: bool
    - dmarc_record: str | None
    - email_security_tier: EmailSecurityTier

  - EmailSecurityTier (StrEnum: STRONG/MODERATE/WEAK/NONE)

Interface: WhoisClient
  async lookup_domain(domain: str) -> WhoisData
    - Wraps python-whois library in asyncio.to_thread()
    - Handles WHOIS_TIMEOUT_SECONDS timeout
    - Applies privacy heuristic: checks for privacy keywords or dual None fields (GDPR)
    - Maps exceptions: timeout → DomainIntelTimeoutError, socket/parse errors → DomainIntelLookupError
    - Sanitizes error messages: excludes raw server response text

Interface: DNSAnalyzer
  async analyze_dns_security(domain: str) -> DnsSecurityPosture
    - Wraps dnspython resolver in asyncio.to_thread()
    - Queries SPF (TXT) and DMARC (_dmarc prefix) records
    - Classifies email security tier based on SPF+DMARC presence:
      - STRONG: both SPF and DMARC present
      - MODERATE: SPF only or DMARC only
      - WEAK: neither present but domain has MX records
      - NONE: no MX records
    - Handles timeout and lookup errors gracefully

Interface: DomainIntelModule (implements BaseModule)
  name -> "domain_intel"
  async execute(inputs: ScanInputs, config: DomainIntelModuleConfig) -> ModuleResult
    - Extracts domain from email or calls _extract_domain() on full_name
    - Calls WhoisClient.lookup_domain() and DNSAnalyzer.analyze_dns_security()
    - Partial success: success=True if either WHOIS or DNS succeeds
    - Aggregates findings via _build_findings(whois_data, dns_posture)
    - Error handling: continues if one operation fails, captures errors

  Private methods:
  - _extract_domain(email: str) -> str
    Simple email regex extraction: everything after "@"

  - _build_findings(whois: WhoisData | None, dns: DnsSecurityPosture | None) -> list[ModuleFinding]
    Generates findings based on domain registrant privacy and DNS security
    Examples:
    - PRIVACY_PROTECTED when privacy_protected=True
    - WEAK_EMAIL_SECURITY when email_security_tier != STRONG
    - Missing DMARC when only SPF present

Module helper functions (prevent code duplication):
  - _detect_privacy(registrant_name: str | None, registrant_org: str | None) -> bool
    Returns True if either field contains privacy keywords or both are None

  - _coerce_first(items: list[Any] | None, default: Any) -> Any
    Returns first item or default; handles None gracefully

  - _coerce_list(value: str | list[str] | None, default: list[str]) -> list[str]
    Normalizes string or list inputs to list

  - _coerce_date(date_str: str | None) -> datetime | None
    Parses date string to datetime; returns None on parse error

Key design decisions:
  - asyncio.to_thread() for all blocking third-party calls (whois, dnspython)
  - Privacy heuristic via keyword set avoids false HIGH findings for legitimate privacy services
  - Partial success (success=True when either WHOIS or DNS succeeds) prevents loss of data
  - Error messages sanitized: no server response text (L007 analog, prevent PII)
  - DNS STRONG tier requires both SPF and DMARC to encourage strong email authentication

Configuration: DomainIntelModuleConfig (frozen dataclass)
  - timeout_seconds: float = 30.0
  - check_privacy: bool = True (enable privacy heuristic)
```

### 4.3e EntityResolver for name collision disambiguation (Task T3.3)

```
Status: CREATED (Task T3.3)
File: src/piea/modules/search.py

Data model: DisambiguationResult (frozen dataclass, slots=True)
  - matched_results: list[SearchResult]
  - is_common_name: bool
  - has_secondary_signals: bool
  - filtered_count: int

Configuration constant:
  - COMMON_NAME_RESULT_THRESHOLD: int = 100 (documented SRS traceability; pre-filter indicator)
  - COMMON_NAMES: frozenset[str] (≈190 US Census common first names, lowercase)

Interface: EntityResolver
  is_common_name(first_name: str | None) -> bool
    Returns True if first_name is in COMMON_NAMES frozenset (case-insensitive lookup)

  extract_signals(result: SearchResult, extra_signals: list[str] | None) -> list[str]
    Extracts secondary signals from result: domain, TLD, title keywords, snippet keywords
    Combines with extra_signals (e.g., employer, location) if provided
    Returns deduplicated signal list

  result_matches_signal(result: SearchResult, signal: str) -> bool
    Returns True if signal appears in result title, snippet, or URL (case-insensitive)
    Substring matching; no exact-match requirement

  filter_results(results: list[SearchResult], subject_name: str | None,
                 extra_signals: list[str] | None) -> DisambiguationResult
    Core disambiguation algorithm:
    1. Extract first_name from subject_name
    2. Check is_common_name(first_name)
    3. For each result, extract signals and check result_matches_signal()
    4. Return DisambiguationResult with filtered list and metadata

Integration with SearchModule:
  - SearchModule.__init__ accepts optional resolver: EntityResolver | None
  - In _aggregate_results(), resolver.filter_results() is called on FOUND result list
  - Filtered findings use disambiguation metadata for severity adjustment:
    - Common name + no secondary signals → INFO severity (low_confidence=True)
    - Other cases → severity unchanged
  - Data broker findings are generated from unfiltered results (false negative prevention)

Key design decisions:
  - Name-list heuristic deterministic and testable (not runtime frequency count)
  - Common names receive INFO severity only if zero secondary signals match
  - Data broker results bypass disambiguation (always from full result set)
  - extra_signals parameter allows future caller-supplied signals (employer, location)
```

### 4.3f Hunter.io email pattern lookup module (Task T3.6)

```
Status: CREATED (Task T3.6)
File: src/piea/modules/hunter.py

Constants:
  - REQUEST_INTERVAL_SECONDS: float = 1.0 (enforced rate limit between API calls)
  - MAX_BATCH_SIZE: int = 100 (max results per domain-search request)
  - HUNTER_API_TIMEOUT_SECONDS: float = 30.0 (per-request timeout)

Exceptions:
  - HunterAPIError (base domain error for Hunter.io API failures)
    Raised with `from None` to drop exception chain and prevent URL leaking (L007 pattern)

Data models:
  - EmailPattern (frozen dataclass)
    - email: str (full email address)
    - first_name: str | None
    - last_name: str | None
    - position: str | None
    - company: str (company name)
    - seniority: str | None (junior, middle, senior, executive, etc.)
    - department: str | None
    - linkedin_url: str | None
    - confidence: float (Hunter's confidence score 0.0-1.0)
    - last_seen_on_the_web: str | None (ISO date string)

Interface: HunterClient
  __init__(api_key: str)
    Stores Hunter.io API key; creates httpx.AsyncClient
    Initializes asyncio.Semaphore(1) for rate limiting

  async domain_search(domain: str, limit: int = 100) -> list[EmailPattern]
    Calls /v2/domain-search endpoint with domain parameter
    Applies batch limiting; maximum limit=MAX_BATCH_SIZE
    Returns up to `limit` EmailPattern objects from "emails" array in API response
    Handles rate-limit (429 status) gracefully — returns empty list
    On non-429 errors: raises HunterAPIError with sanitized message (no URL)

  async email_finder(domain: str, first_name: str | None, last_name: str | None) -> EmailPattern | None
    Calls /v2/email-finder endpoint with domain, first_name (optional), last_name (optional)
    Skipped if full_name has fewer than 2 tokens (requires first + last)
    Returns single EmailPattern if found; None if not found
    On 404 (not found): returns None (not an error)
    On timeout or non-404 errors: raises HunterAPIError

  async close() -> None
    Calls await client.close() to release HTTP connection

Key design decisions:
  - Rate limit sleep (REQUEST_INTERVAL_SECONDS) in finally block inside semaphore (L009)
  - HunterAPIError raised with `from None` to prevent chain containing full URL with API key (L007)
  - _parse_name_parts() returns None for single-token names (Hunter requires first+last)
  - email_finder skipped if full_name has < 2 tokens; success=True if domain_search succeeds
  - Partial success logic: success=True when at least one of domain-search or email-finder succeeds
  - Findings generated:
    1. email_pattern_found (type, INFO severity, domain-search result)
    2. email_addresses_exposed (type, MEDIUM severity, when confidence >= 70)
    3. email_address_confirmed (type, MEDIUM severity, email-finder result with confidence >= 70)

Interface: HunterModule (implements BaseModule)
  name -> "hunter"
  async execute(inputs: ScanInputs, config: HunterModuleConfig) -> ModuleResult
    - Validates domain availability: requires email or full_name with @ or domain extraction
    - Calls client.domain_search(domain, limit=100) for primary email enumeration
    - Calls client.email_finder(domain, first_name, last_name) for targeted lookup if full_name available
    - Aggregates findings from both operations via _aggregate_results()
    - Partial success: success=True if at least one operation succeeds
    - Rate-limit and timeout errors captured in errors list; continue execution

  Private methods:
  - _get_domain(inputs: ScanInputs) -> str | None
    Extracts domain from email (after "@") or validates caller-provided domain

  - _parse_name_parts(full_name: str | None) -> tuple[str | None, str | None]
    Splits full_name on whitespace; returns (first, last) or (None, None) if < 2 tokens

  - async _aggregate_results(domain: str, domain_search: list[EmailPattern],
                            email_pattern: EmailPattern | None) -> list[ModuleFinding]
    Builds findings from domain_search results and email_finder result
    Applies confidence thresholds for severity assessment

Configuration: HunterModuleConfig (frozen dataclass)
  - api_key: str (Hunter.io API key — required)
  - domain_search_limit: int = 100 (max results to fetch)
  - confidence_threshold: float = 70.0 (% confidence minimum for MEDIUM severity)
  - timeout_seconds: float = 30.0

Module helper functions:
  - _categorize_email_finding(email_pattern: EmailPattern) -> Severity
    Returns MEDIUM if confidence >= threshold; LOW otherwise
```

### 4.3g HIBP paste-account exposure module (Task T3.7)

```
Status: CREATED (Task T3.7)
File: src/piea/modules/paste_monitor.py

Constants:
  - HIBP_PASTE_BASE: str = "https://haveibeenpwned.com/api/v3/pasteaccount"
  - USER_AGENT: str = "PIEA-SecurityScanner/1.0"
  - REQUEST_INTERVAL_SECONDS: float = 1.6 (HIBP minimum 1500ms, buffer for 1.6s rate limiting)

Exceptions:
  - PasteMonitorError (base domain error)
  - PasteMonitorAPIError (non-2xx, non-404 response; `from None` to prevent URL/PII leaking per L007/L016)
  - PasteMonitorTimeoutError (request timeout)
  - PasteMonitorRateLimitError (HTTP 429; contains optional retry_after value)

Data models:
  - PasteRecord (frozen dataclass, slots=True)
    - source: str (paste site name, e.g., "Pastebin", "Ghostbin")
    - title: str | None (paste title)
    - paste_id: str | None (site-specific identifier)
    - paste_date: str | None (ISO 8601 date string)
    - email_count: int (number of email addresses in paste)

Interface: PasteClient
  __init__(api_key: str, http_client: httpx.AsyncClient | None = None)
    Stores API key; creates or wraps httpx.AsyncClient
    Initializes asyncio.Semaphore(1) for rate limiting
    Tracks ownership of HTTP client for cleanup

  async get_paste_exposure(email: str) -> list[PasteRecord]
    Calls HIBP paste-account endpoint with email as URL path segment
    HTTP 404 treated as clean result → returns empty list (no pastes found)
    HTTP 429 → raises PasteMonitorRateLimitError
    Other errors → raises PasteMonitorAPIError with sanitized message (no URL/email)
    Rate-limit sleep (REQUEST_INTERVAL_SECONDS) enforced in finally block (L009)

  async close() -> None
    Closes underlying HTTP client if owned by this instance

  Private methods:
  - async _make_request(email: str) -> list[dict[str, Any]]
    Executes GET request to HIBP endpoint
    Enforces inter-request interval inside semaphore (L009)
    Maps HTTP errors to typed exceptions without URL exposure (L007/L016)
    Returns empty list on 404 (clean result)

  - _parse_response(raw: list[dict[str, Any]]) -> list[PasteRecord]
    Parses HIBP JSON response into PasteRecord objects (L003 compliant)
    Handles missing/malformed fields gracefully (defaults: title=None, paste_id=None, etc.)

Interface: PasteMonitor (implements BaseModule)
  name -> "paste_monitor"

  async execute(inputs: ScanInputs) -> ModuleResult
    - Validates API key configured; returns error if absent
    - Validates email address provided; returns error if absent
    - Calls _run_paste_check(email) to fetch paste records
    - Calls _build_findings(pastes) to convert records to ModuleFindings
    - Returns ModuleResult with findings + metadata (paste_count)

  Private methods:
  - async _run_paste_check(email: str) -> tuple[list[PasteRecord], list[str]]
    Catches PasteMonitorError and converts to error strings (logging + graceful failure)
    Returns (pastes, errors) tuple

  - _build_findings(pastes: list[PasteRecord]) -> list[ModuleFinding]
    Emits one HIGH-severity finding per paste (FR-7.1 per-paste granularity)
    Finding type: "paste_exposure"
    Category: "paste_site"
    Evidence includes: source, title, paste_id, paste_date, email_count
    Remediation: "Check paste site, change password if credentials exposed"
    Weight: 0.85 (HIGH severity)

Key design decisions:
  - HTTP 404 treated as success (clean result) — not an error
  - Rate-limit sleep in finally block inside semaphore (L009 compliance)
  - PasteMonitorAPIError raised with `from None` to drop exception chain (L007/L016 compliance)
  - Email never exposed in exception messages or logs
  - One HIGH finding per paste encourages per-paste review and remediation
  - HIBP API key via hibp-api-key request header (not query param)
  - No new dependencies; reuses settings.hibp_api_key (shared with HIBPModule)
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
# PROJECT_STATE.md — Living Project Context (Self-Managed by Claude Code)

**Purpose:** This file is Claude Code's persistent memory. It prevents hallucination, context drift, and contradictory decisions across tasks. Claude Code must read this file before starting any task and update it after completing any task.

**Last updated:** 2026-03-21 — Security Workflow Setup
**Updated by:** Claude Code
**Current phase:** Phase 0 — Project setup and ethical foundation
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
│       │   ├── cache.py                [Status: not created]
│       │   └── audit.py                [Status: not created]
│       ├── modules/
│       │   ├── __init__.py             [Status: not created]
│       │   ├── base.py                 [Status: not created]
│       │   ├── hibp.py                 [Status: not created]
│       │   ├── username_enum.py        [Status: not created]
│       │   ├── graph_crawler.py        [Status: not created]
│       │   ├── search.py              [Status: not created]
│       │   ├── domain_intel.py         [Status: not created]
│       │   ├── paste_monitor.py        [Status: not created]
│       │   └── extractors/
│       │       ├── __init__.py         [Status: not created]
│       │       ├── github.py           [Status: not created]
│       │       ├── mastodon.py         [Status: not created]
│       │       ├── keybase.py          [Status: not created]
│       │       ├── gitlab.py           [Status: not created]
│       │       ├── gravatar.py         [Status: not created]
│       │       ├── reddit.py           [Status: not created]
│       │       └── bio_parser.py       [Status: not created]
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
│   ├── platforms.json                  [Status: not created]
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
│   │   └── test_scan_request.py       [Status: created — T0.6]
│   └── integration/
│       └── __init__.py                 [Status: created — T0.6]
└── docs/                               [Status: not created — Phase 7]
```

**File count:** 35 created / ~65 planned
**Last hierarchy update:** 2026-03-21

---

## 3. Implementation status

### 3.1 Phase completion tracker

| Phase | Name | Status | Tasks done | Tasks total | Milestone verified |
|-------|------|--------|-----------|------------|-------------------|
| 0 | Project setup & ethics | COMPLETE | 7 | 7 | No — pending `docker compose up` verification |
| 1 | Breach exposure module | NOT STARTED | 0 | 6 | No |
| 2 | Username enum & graph crawler | NOT STARTED | 0 | 14 | No |
| 3 | Search & domain intelligence | NOT STARTED | 0 | 8 | No |
| 4 | Risk scoring engine | NOT STARTED | 0 | 7 | No |
| 5 | Scan orchestration & API | NOT STARTED | 0 | 7 | No |
| 6 | Frontend & report UI | NOT STARTED | 0 | 12 | No |
| 7 | Hardening & documentation | NOT STARTED | 0 | 8 | No |

### 3.2 Current task queue

```
NEXT UP:    T1.1 — Implement HIBP API v3 client (Phase 1 begins)
AFTER THAT: T1.2 — Build breach data parser and severity classifier
AFTER THAT: T1.3 — Implement password hash check (k-anonymity model)
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

---

## 4. Established interfaces and contracts

**CRITICAL: Once an interface is established and other code depends on it, it must not change without updating ALL dependents. Track every interface here.**

### 4.1 Base module interface

```
Status: NOT YET CREATED (Task T2.1)
File: src/piea/modules/base.py
Contract: TBD
Implemented by: (none yet)
```

### 4.2 Data models registry

**Track every dataclass and Pydantic model here once created. Include the exact field names and types so future tasks reference the real implementation, not the SRS specification.**

```
Status: NO MODELS CREATED YET

When models are created, log them here in this format:

MODEL: IdentityNode
FILE: src/piea/graph/models.py
CREATED AT: Task T2.11
FIELDS:
  - platform: str
  - identifier: str
  - profile_url: str
  - confidence: float
  - discovered_at_depth: int
  - raw_data: dict[str, object]
USED BY: graph_crawler.py, serializer.py, orchestrator.py
```

### 4.3 API endpoint registry

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

### 4.4 Database table registry

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

### 4.5 Exception hierarchy

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
| (none yet) | | | | |

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

Status: No dependencies logged yet — will be populated as tasks complete.

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
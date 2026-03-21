# Project Plan — Public Information Exposure Analyzer (PIEA)

**Version:** 1.0  
**Date:** 2026-03-21  
**Author:** Security Engineering Team  
**Status:** Planning Phase

---

## 1. Executive summary

The Public Information Exposure Analyzer (PIEA) is a consent-based security assessment tool that aggregates publicly available information about an individual from legitimate data sources, builds a recursive identity graph across platforms, and produces a risk-scored exposure report with actionable remediation recommendations.

The tool is designed for personal self-assessment, authorized penetration testing, and security awareness training. It does not scrape private data, bypass authentication mechanisms, or violate platform terms of service.

---

## 2. Project objectives

| ID | Objective | Success metric |
|----|-----------|---------------|
| OBJ-1 | Build a modular OSINT aggregation engine | Minimum 6 independent data source modules operational |
| OBJ-2 | Implement recursive identity graph crawling | Graph expansion across 3+ depth levels with cycle detection |
| OBJ-3 | Develop a weighted risk scoring algorithm | Produce consistent, reproducible scores across identical inputs |
| OBJ-4 | Deliver an interactive web-based report | Report renders in browser with findings grouped by severity |
| OBJ-5 | Enforce consent and ethical boundaries | Every scan requires documented consent before execution |
| OBJ-6 | Maintain legal compliance | No platform TOS violations, GDPR/PDPD-aligned data handling |

---

## 3. Scope

### 3.1 In scope

- Username enumeration across 300+ public platforms (HTTP status check)
- Recursive cross-platform identity linking via public APIs (GitHub, Mastodon, Keybase, GitLab, Gravatar, Reddit)
- Email breach exposure analysis via Have I Been Pwned API v3
- Domain intelligence (WHOIS, DNS records, email security posture)
- Public search footprint analysis via Google Custom Search API
- Paste site monitoring for exposed credentials
- Weighted risk scoring engine with configurable weights
- Web-based report with findings, risk score, and remediation steps
- Consent gate enforced before any scan begins
- Scan audit logging with timestamps
- REST API backend with OpenAPI documentation
- Dockerized deployment

### 3.2 Out of scope

- Scraping private or authentication-protected profile content
- Bypassing platform anti-bot protections or CAPTCHAs
- Accessing Facebook, Instagram, LinkedIn, or TikTok private APIs
- Dark web monitoring (requires specialized infrastructure and licensing)
- Real-time continuous monitoring (this is a point-in-time scanner)
- Mobile application
- Multi-tenancy or user account management
- Payment processing or commercial licensing

---

## 4. Technology stack

| Layer | Technology | Version | Justification |
|-------|-----------|---------|--------------|
| Language | Python | 3.11+ | Best OSINT library ecosystem, async support |
| Backend framework | FastAPI | 0.110+ | Async-native, auto-generated OpenAPI docs, dependency injection |
| HTTP client | httpx | 0.27+ | Async HTTP with connection pooling, timeout control |
| Task queue | Celery + Redis | 5.3+ / 7+ | Background scan execution, progress tracking |
| Database | PostgreSQL | 16+ | Scan results storage, audit logs, graph persistence |
| ORM | SQLAlchemy | 2.0+ | Async support, type-safe queries |
| Migration | Alembic | 1.13+ | Database schema versioning |
| Caching | Redis | 7+ | API response caching, rate limit state |
| Frontend | React | 18+ | Component-based report rendering |
| Charting | Recharts | 2.12+ | Risk visualization, graph rendering |
| Graph visualization | D3.js | 7+ | Identity graph network display |
| Containerization | Docker + Docker Compose | 24+ | Reproducible deployment |
| Testing | pytest + pytest-asyncio | 8+ | Async test support, fixtures |
| Linting | ruff | 0.3+ | Fast Python linter and formatter |
| Type checking | mypy | 1.9+ | Static type analysis |

---

## 5. Architecture overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Input    │  │ Progress     │  │ Report Dashboard  │  │
│  │ Form     │  │ Tracker      │  │ + Identity Graph  │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API
┌───────────────────────┴─────────────────────────────────┐
│                 Backend (FastAPI)                         │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Consent  │  │ Scan         │  │ Report            │  │
│  │ Gate     │  │ Orchestrator │  │ Generator         │  │
│  └──────────┘  └──────┬───────┘  └───────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ Celery Tasks
┌──────────────────────┴──────────────────────────────────┐
│              Data Source Modules (async)                  │
│  ┌────────┐ ┌────────┐ ┌─────────┐ ┌────────────────┐  │
│  │ HIBP   │ │Username│ │ Search  │ │ Domain Intel   │  │
│  │ Module │ │Enum +  │ │ Module  │ │ Module         │  │
│  │        │ │Graph   │ │         │ │                │  │
│  │        │ │Crawler │ │         │ │                │  │
│  └────────┘ └────────┘ └─────────┘ └────────────────┘  │
│  ┌────────┐ ┌────────┐ ┌─────────┐                     │
│  │Paste   │ │Social  │ │ Risk    │                     │
│  │Monitor │ │Bio     │ │ Scoring │                     │
│  │        │ │Parser  │ │ Engine  │                     │
│  └────────┘ └────────┘ └─────────┘                     │
└─────────────────────────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│              Infrastructure                              │
│  ┌────────────┐  ┌──────────┐  ┌────────────────────┐   │
│  │ PostgreSQL │  │ Redis    │  │ Rate Limiter       │   │
│  │ (storage)  │  │ (cache)  │  │ (per-API tracking) │   │
│  └────────────┘  └──────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Project phases and timeline

### Phase 0 — Project setup and ethical foundation (Week 1)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T0.1 | Initialize Python project with pyproject.toml, ruff, mypy config | Project skeleton | 2 |
| T0.2 | Set up Docker Compose (PostgreSQL, Redis, FastAPI) | docker-compose.yml | 3 |
| T0.3 | Create database schema and Alembic migrations | Initial migration files | 3 |
| T0.4 | Implement consent gate module | ConsentService with audit logging | 4 |
| T0.5 | Build API scaffolding (health check, scan endpoints) | FastAPI app with routers | 3 |
| T0.6 | Set up pytest fixtures and CI pipeline | Test infrastructure | 3 |
| T0.7 | Write LEGAL.md with terms of use and disclaimer | Legal documentation | 2 |

**Milestone M0:** Project boots with `docker compose up`, health endpoint responds, consent gate blocks scans without valid consent record.

---

### Phase 1 — Breach exposure module (Week 2)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T1.1 | Implement HIBP API v3 client with API key auth | HIBPClient class | 4 |
| T1.2 | Build breach data parser and severity classifier | BreachAnalyzer class | 3 |
| T1.3 | Implement password hash check (k-anonymity model) | PwnedPasswordChecker | 3 |
| T1.4 | Add response caching (Redis, 24h TTL for breach data) | CacheLayer integration | 2 |
| T1.5 | Write unit tests with mocked API responses | Test suite for HIBP module | 3 |
| T1.6 | Build breach findings data model | BreachFinding dataclass | 2 |

**Milestone M1:** Given an email address, the system returns a structured list of breaches with severity classifications.

---

### Phase 2 — Username enumeration and identity graph crawler (Weeks 3–4)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T2.1 | Build platform registry (300+ sites with URL patterns, expected status codes, platform metadata) | platforms.json config | 6 |
| T2.2 | Implement async username checker with connection pooling | UsernameEnumerator class | 5 |
| T2.3 | Build per-platform rate limiter (token bucket algorithm) | RateLimiter class | 4 |
| T2.4 | Implement GitHub API profile extractor | GitHubExtractor class | 3 |
| T2.5 | Implement Mastodon API profile extractor (multi-instance) | MastodonExtractor class | 4 |
| T2.6 | Implement Keybase API profile extractor | KeybaseExtractor class | 2 |
| T2.7 | Implement GitLab API profile extractor | GitLabExtractor class | 2 |
| T2.8 | Implement Gravatar API profile extractor | GravatarExtractor class | 2 |
| T2.9 | Implement Reddit API profile extractor | RedditExtractor class | 2 |
| T2.10 | Build bio/text link parser (regex-based cross-platform identifier extraction) | BioLinkParser class | 5 |
| T2.11 | Implement identity graph data model (nodes, edges, confidence scores) | IdentityGraph class | 4 |
| T2.12 | Build recursive graph crawler with depth control, cycle detection, and visited-set tracking | GraphCrawler class | 8 |
| T2.13 | Add crawl timeout (wall-clock limit per scan) | Timeout middleware | 2 |
| T2.14 | Write integration tests with recorded API responses | Test suite for graph crawler | 6 |

**Milestone M2:** Given a seed username, the system builds an identity graph spanning multiple platforms with recursive discovery of linked accounts up to depth 3.

---

### Phase 3 — Search and domain intelligence modules (Week 5)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T3.1 | Implement Google Custom Search API client | SearchClient class | 3 |
| T3.2 | Build search result categorizer (social, news, professional, forum, cached) | ResultCategorizer class | 4 |
| T3.3 | Implement entity disambiguation logic (name collision handling via secondary signals) | EntityResolver class | 5 |
| T3.4 | Implement WHOIS lookup client | WhoisClient class | 3 |
| T3.5 | Implement DNS record analyzer (MX, TXT, SPF, DKIM, DMARC) | DNSAnalyzer class | 4 |
| T3.6 | Implement Hunter.io email pattern lookup | HunterClient class | 2 |
| T3.7 | Build paste site checker (Pastebin, GitHub Gist public search) | PasteMonitor class | 3 |
| T3.8 | Write unit and integration tests | Test suite for Phase 3 modules | 4 |

**Milestone M3:** All data source modules operational. Given a name, email, and username, the system queries all sources concurrently and returns structured findings.

---

### Phase 4 — Risk scoring engine (Week 6)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T4.1 | Define risk taxonomy (finding types, severity levels, weight matrix) | risk_taxonomy.json | 3 |
| T4.2 | Implement weighted scoring algorithm | RiskScorer class | 5 |
| T4.3 | Build risk tier classifier (low, moderate, high, critical) | TierClassifier class | 2 |
| T4.4 | Implement per-finding remediation recommendation engine | RemediationEngine class | 4 |
| T4.5 | Build score breakdown generator (category-level subtotals) | ScoreBreakdown class | 3 |
| T4.6 | Add configurable weight overrides (admin can adjust weights) | WeightConfig loader | 2 |
| T4.7 | Write scoring tests with known-outcome fixtures | Test suite for scoring | 4 |

**Milestone M4:** The system produces a numeric risk score (0–100), a risk tier, a category breakdown, and remediation recommendations for every finding.

---

### Phase 5 — Scan orchestration and API (Week 7)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T5.1 | Implement Celery task for full scan orchestration | ScanTask class | 5 |
| T5.2 | Build scan progress tracking (WebSocket or polling) | ProgressTracker class | 4 |
| T5.3 | Implement scan result persistence (PostgreSQL) | ScanResultRepository | 3 |
| T5.4 | Build REST API endpoints (create scan, get status, get report) | API router | 4 |
| T5.5 | Add scan rate limiting (max 10 scans/hour per client IP) | ScanRateLimiter | 2 |
| T5.6 | Implement scan audit logging | AuditLogger class | 2 |
| T5.7 | Write API integration tests | Test suite for API | 4 |

**Milestone M5:** End-to-end scan works: submit input via API, receive scan ID, poll for progress, retrieve completed report.

---

### Phase 6 — Frontend and report UI (Weeks 8–9)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T6.1 | Set up React project with Vite, TailwindCSS | Frontend skeleton | 2 |
| T6.2 | Build input form with consent checkbox and validation | InputForm component | 4 |
| T6.3 | Build scan progress indicator (animated, real-time) | ProgressBar component | 3 |
| T6.4 | Build report dashboard layout (header, score gauge, sections) | ReportDashboard component | 5 |
| T6.5 | Build risk score gauge visualization | ScoreGauge component (Recharts) | 3 |
| T6.6 | Build findings list with severity badges and expandable details | FindingsList component | 5 |
| T6.7 | Build identity graph network visualization | IdentityGraph component (D3.js) | 8 |
| T6.8 | Build remediation recommendations panel | RemediationPanel component | 3 |
| T6.9 | Build scan history page | ScanHistory component | 3 |
| T6.10 | Implement PDF report export | PDFExporter utility | 4 |
| T6.11 | Responsive design and accessibility pass | CSS adjustments | 3 |
| T6.12 | Write component tests | Frontend test suite | 4 |

**Milestone M6:** Complete web UI functional. User can input data, watch scan progress, view interactive report with identity graph visualization, and export to PDF.

---

### Phase 7 — Hardening, testing, and documentation (Week 10)

| Task | Description | Deliverable | Est. hours |
|------|------------|-------------|------------|
| T7.1 | Security audit (input validation, injection prevention, API key protection) | Security review report | 4 |
| T7.2 | Performance testing (concurrent scans, API rate limit behavior) | Performance test results | 3 |
| T7.3 | End-to-end integration tests | E2E test suite | 5 |
| T7.4 | Write user documentation (how to use, what it checks, limitations) | USER_GUIDE.md | 3 |
| T7.5 | Write developer documentation (architecture, adding modules, API reference) | DEVELOPER_GUIDE.md | 3 |
| T7.6 | Write deployment guide (Docker, environment variables, API keys) | DEPLOYMENT.md | 2 |
| T7.7 | Add health monitoring and error alerting | Healthcheck endpoints | 2 |
| T7.8 | Final code review and cleanup | Clean codebase | 3 |

**Milestone M7:** Production-ready release. All tests pass, documentation complete, security reviewed, deployment guide available.

---

## 7. Risk register

| Risk ID | Risk | Probability | Impact | Mitigation |
|---------|------|-------------|--------|-----------|
| R1 | HIBP API changes pricing or availability | Low | High | Abstract API client behind interface; have fallback breach databases identified |
| R2 | Platform blocks automated requests (rate limiting, IP bans) | High | Medium | Implement respectful rate limiting, use API keys where available, rotate user agents |
| R3 | Legal challenge from platform regarding TOS | Low | High | Strict adherence to public APIs only; document that no scraping occurs; legal disclaimer |
| R4 | False positive in entity resolution (wrong person matched) | Medium | Medium | Confidence scoring on all findings; require secondary signal for entity matching; allow user to dispute findings |
| R5 | API key exposure in client-side code | Medium | Critical | All API keys server-side only; environment variables; never in frontend |
| R6 | Tool misuse for unauthorized surveillance | Medium | High | Consent gate enforcement; scan audit logging; rate limiting; terms of use |
| R7 | Graph crawler enters infinite loop or exponential expansion | Medium | Medium | Depth limit (max 3), visited-set, wall-clock timeout (60s), max-nodes limit (500) |
| R8 | Stale cached data leads to inaccurate report | Low | Low | Cache TTL (24h for breach data, 1h for profile data); manual cache clear option |

---

## 8. API key requirements

| Service | Key type | Cost | Required for | How to obtain |
|---------|----------|------|-------------|--------------|
| Have I Been Pwned | API key | ~$3.50/month | Breach checks | haveibeenpwned.com/API/Key |
| Google Custom Search | API key + Search Engine ID | Free (100 queries/day) | Public search results | console.cloud.google.com |
| GitHub | Personal access token | Free | Higher rate limits (5000/hr vs 60/hr) | github.com/settings/tokens |
| Hunter.io | API key | Free tier (25 lookups/month) | Email pattern discovery | hunter.io/api |
| Steam | Web API key | Free | Steam profile data | steamcommunity.com/dev/apikey |
| Reddit | OAuth app credentials | Free | Reddit profile data | reddit.com/prefs/apps |

---

## 9. Definition of done

A feature is considered done when all of the following are satisfied:

1. Code is written, type-annotated, and passes mypy strict mode
2. Unit tests cover happy path, error cases, and edge cases (minimum 80% coverage)
3. Integration test with recorded API responses passes
4. Code passes ruff linting with zero warnings
5. Function/class has a docstring explaining purpose, parameters, and return type
6. If it's an API endpoint, it's documented in the OpenAPI schema
7. If it's a data source module, it handles API errors gracefully (timeout, rate limit, 404, 500)
8. Code has been reviewed by at least one other team member (or self-reviewed with a 24h gap)

---

## 10. Folder structure

```
piea/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
├── src/
│   └── piea/
│       ├── __init__.py
│       ├── main.py                     # FastAPI app entry point
│       ├── config.py                   # Settings from environment
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── scans.py            # POST /scans, GET /scans/{id}
│       │   │   ├── reports.py          # GET /reports/{scan_id}
│       │   │   └── health.py           # GET /health
│       │   ├── schemas/
│       │   │   ├── scan_request.py     # Pydantic input models
│       │   │   ├── scan_response.py    # Pydantic output models
│       │   │   └── report.py           # Report response model
│       │   └── dependencies.py         # FastAPI dependency injection
│       ├── core/
│       │   ├── __init__.py
│       │   ├── consent.py              # Consent gate service
│       │   ├── orchestrator.py         # Scan orchestration logic
│       │   ├── rate_limiter.py         # Per-API rate limiting
│       │   ├── cache.py                # Redis cache layer
│       │   └── audit.py                # Audit logging
│       ├── modules/
│       │   ├── __init__.py
│       │   ├── base.py                 # Abstract base for all modules
│       │   ├── hibp.py                 # Have I Been Pwned module
│       │   ├── username_enum.py        # Username enumeration
│       │   ├── graph_crawler.py        # Recursive identity graph crawler
│       │   ├── search.py               # Google Custom Search module
│       │   ├── domain_intel.py         # WHOIS + DNS module
│       │   ├── paste_monitor.py        # Paste site checker
│       │   └── extractors/
│       │       ├── __init__.py
│       │       ├── github.py           # GitHub API extractor
│       │       ├── mastodon.py         # Mastodon API extractor
│       │       ├── keybase.py          # Keybase API extractor
│       │       ├── gitlab.py           # GitLab API extractor
│       │       ├── gravatar.py         # Gravatar API extractor
│       │       ├── reddit.py           # Reddit API extractor
│       │       └── bio_parser.py       # Free-text link extractor
│       ├── scoring/
│       │   ├── __init__.py
│       │   ├── risk_scorer.py          # Weighted scoring algorithm
│       │   ├── tier_classifier.py      # Risk tier classification
│       │   ├── remediation.py          # Remediation recommendations
│       │   └── taxonomy.py             # Risk taxonomy definitions
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── models.py              # IdentityNode, IdentityEdge, IdentityGraph
│       │   └── serializer.py          # Graph to JSON/D3 format
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py              # SQLAlchemy ORM models
│       │   ├── session.py             # Database session management
│       │   └── repositories/
│       │       ├── scan_repo.py
│       │       └── audit_repo.py
│       └── tasks/
│           ├── __init__.py
│           └── scan_task.py            # Celery background task
├── config/
│   ├── platforms.json                  # Platform registry (300+ sites)
│   └── risk_taxonomy.json              # Risk weights and categories
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── ScanPage.tsx
│   │   │   ├── ReportPage.tsx
│   │   │   └── HistoryPage.tsx
│   │   ├── components/
│   │   │   ├── InputForm.tsx
│   │   │   ├── ConsentGate.tsx
│   │   │   ├── ProgressBar.tsx
│   │   │   ├── ScoreGauge.tsx
│   │   │   ├── FindingsList.tsx
│   │   │   ├── IdentityGraphViz.tsx
│   │   │   └── RemediationPanel.tsx
│   │   └── api/
│   │       └── client.ts
│   └── public/
├── tests/
│   ├── conftest.py
│   ├── fixtures/                       # Recorded API responses
│   │   ├── hibp_response.json
│   │   ├── github_profile.json
│   │   ├── mastodon_profile.json
│   │   └── ...
│   ├── unit/
│   │   ├── test_hibp.py
│   │   ├── test_username_enum.py
│   │   ├── test_graph_crawler.py
│   │   ├── test_risk_scorer.py
│   │   ├── test_bio_parser.py
│   │   └── ...
│   └── integration/
│       ├── test_scan_api.py
│       └── test_full_scan.py
├── docs/
│   ├── USER_GUIDE.md
│   ├── DEVELOPER_GUIDE.md
│   ├── DEPLOYMENT.md
│   └── API_REFERENCE.md
├── LEGAL.md
├── LICENSE
└── README.md
```

---

## 11. Dependency summary

### Python (pyproject.toml)

```
fastapi>=0.110
uvicorn[standard]>=0.29
httpx>=0.27
celery[redis]>=5.3
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29
alembic>=1.13
pydantic>=2.6
pydantic-settings>=2.2
python-whois>=0.9
dnspython>=2.6
redis>=5.0
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=5.0
mypy>=1.9
ruff>=0.3
```

### Frontend (package.json)

```
react>=18
react-dom>=18
react-router-dom>=6
recharts>=2.12
d3>=7
axios>=1.6
tailwindcss>=3.4
vite>=5
typescript>=5.4
vitest>=1.4
```

---

## 12. Environment variables

```env
# Required API keys
HIBP_API_KEY=                          # Have I Been Pwned API key
GOOGLE_CSE_API_KEY=                    # Google Custom Search API key
GOOGLE_CSE_ENGINE_ID=                  # Google Custom Search Engine ID
GITHUB_TOKEN=                          # GitHub personal access token
HUNTER_API_KEY=                        # Hunter.io API key
STEAM_API_KEY=                         # Steam Web API key
REDDIT_CLIENT_ID=                      # Reddit OAuth client ID
REDDIT_CLIENT_SECRET=                  # Reddit OAuth client secret

# Infrastructure
DATABASE_URL=postgresql+asyncpg://piea:password@localhost:5432/piea
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Application
SCAN_MAX_DEPTH=3                       # Maximum graph crawl depth
SCAN_TIMEOUT_SECONDS=120               # Wall-clock timeout per scan
SCAN_MAX_NODES=500                     # Maximum nodes in identity graph
SCAN_RATE_LIMIT_PER_HOUR=10           # Max scans per client IP per hour
CACHE_TTL_BREACH=86400                 # Breach data cache TTL (24 hours)
CACHE_TTL_PROFILE=3600                 # Profile data cache TTL (1 hour)
LOG_LEVEL=INFO
```
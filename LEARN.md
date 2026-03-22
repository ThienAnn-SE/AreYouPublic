# LEARN.md — Accumulated Learnings and Proven Patterns

**Purpose:** Every lesson learned — from failures, successes, or discoveries — is logged here. Claude Code must check this file during Phase 1 (requirement analysis) and Phase 3 (skill assessment) of every task to apply accumulated knowledge.

**How to use:** Before implementing any task, search this file by tags matching the current task's module, library, or pattern. Apply matching learnings to your implementation plan.

---

## Learning index

| ID | Date | Source | Category | Tags | Summary |
|----|------|--------|----------|------|---------|
| L001 | 2026-03-21 | Failure F001 at T1.5 | library | trufflehog, ci, github-actions | TruffleHog Action adds `--fail` automatically — never pass it in `extra_args` |
| L002 | 2026-03-21 | Failure F002 at T1.5 | testing | conftest, postgresql, sqlalchemy, sqlite, ci | Conftest must check `DATABASE_URL` env var first; SQLite needs explicit type overrides for PostgreSQL types |
| L003 | 2026-03-21 | Failure F003 at T1.5 | language | mypy, typing, json, dict | Use `dict[str, Any]` for external JSON dicts; `dict[str, object]` breaks `.get()` calls |
| L004 | 2026-03-21 | Failure F004 at T1.5 | testing | ci, security, secret-scan, regex | Exclude `tests/` from high-entropy string scans — test files need dummy credentials |
| L005 | 2026-03-21 | Failure F005 at T1.5 | testing | coverage, pytest, ci | Match coverage threshold to current project state; raise incrementally per module |
| L006 | 2026-03-21 | Failure F006 at T1.5 | language | ruff, linting, imports | Run `ruff check` on ENTIRE project before commit, not just changed files |
| L007 | 2026-03-21 | Task T1.5 (positive) | security | httpx, error-handling, pii | Catch `httpx.HTTPStatusError` and re-raise as domain error to prevent email leaking in error messages |
| L008 | 2026-03-21 | Task T1.5 (positive) | framework | fastapi, dependency-injection, resource-management | FastAPI DI providers must be async generators with `finally` for resource cleanup |
| L009 | 2026-03-21 | Task T1.5 (positive) | security | asyncio, rate-limiting, semaphore | Rate-limit sleep must be in `finally` block inside semaphore to prevent bypass on exception |
| L010 | 2026-03-21 | Task T2.4 (positive) | pattern | module-design, execute-pattern, result-aggregation | Extract result aggregation logic to dedicated method to keep execute() under 20 lines |
| L011 | 2026-03-21 | Task T2.5 (positive) | pattern | profile-extraction, bio-parsing, regex | Use span tracking in regex extraction to avoid overlapping token matches in bio text |
| L012 | 2026-03-21 | Task T2.6 (positive) | pattern | sqlalchemy, orm, id-generation, unit-testing | Set SQLAlchemy UUID ids explicitly at object construction time for test usability |
| L013 | 2026-03-22 | Task T3.1 (positive) | pattern | module-design, dataclass, constructor-params | Group module configuration into frozen dataclass to keep __init__ under 3-parameter rule |
| L014 | 2026-03-22 | Task T3.1 (positive) | pattern | domain-extraction, string-manipulation | Use removeprefix for domain extraction, not lstrip — lstrip removes chars, removeprefix removes prefix only |
| L015 | 2026-03-22 | Task T3.1 (positive) | testing | test-path-anchoring, pathlib, config-loading | Anchor test paths using Path(__file__).parents[N] instead of hardcoded relative paths |
| L016 | 2026-03-22 | Task T3.2 (positive) | pattern | domain-matching, subdomain, categorization | Check both full domain and registered domain when matching — subdomains like news.ycombinator.com are semantically distinct |
| L017 | 2026-03-22 | Task T3.2 (positive) | pattern | config-driven, json, extensibility | Put classification rules in JSON config (not hardcoded) to allow domain/keyword updates without code changes |

---

## Learning entries

## L001 — TruffleHog Action adds `--fail` and `--no-update` automatically

**Date:** 2026-03-21
**Source:** Failure F001 at Task T1.5
**Category:** library
**Tags:** trufflehog, ci, github-actions, security-scan

### Learning
The `trufflesecurity/trufflehog` GitHub Action's internal wrapper script automatically appends `--fail` and `--no-update` to every scan invocation. Passing either flag again in `extra_args` causes a "flag cannot be repeated" error and crashes the job.

### Rule
Never pass `--fail` or `--no-update` in TruffleHog Action `extra_args`. Only pass scan-behavior flags like `--only-verified`, `--results=verified,unknown`, or `--exclude-paths`.

### Example
```yaml
# BEFORE (crashes with duplicate flag error)
- uses: trufflesecurity/trufflehog@main
  with:
    extra_args: --only-verified --fail

# AFTER (correct)
- uses: trufflesecurity/trufflehog@main
  with:
    extra_args: --only-verified
```

### Applies to
Any task that modifies `.github/workflows/security.yml` or adds a TruffleHog scan step.

---

## L002 — Conftest must prioritize `DATABASE_URL` env var over SQLite fallback

**Date:** 2026-03-21
**Source:** Failure F002 at Task T1.5
**Category:** testing
**Tags:** conftest, postgresql, sqlalchemy, sqlite, ci, inet, jsonb

### Learning
CI provides a real PostgreSQL service and sets `DATABASE_URL`. If conftest hardcodes SQLite, PostgreSQL-specific ORM types (`INET`, `JSONB`, `UUID`) cause `visit_INET`/`visit_JSONB` errors at schema creation time. The fix is to use `DATABASE_URL` when available, and register SQLite type compiler overrides as a local dev fallback.

### Rule
Always check `os.environ.get("DATABASE_URL")` first in conftest. When falling back to SQLite, register type compilation overrides for every PostgreSQL-specific type used in any ORM model.

### Example
```python
# BEFORE (SQLite only — crashes in CI on INET/JSONB types)
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# AFTER (CI-aware with SQLite type overrides)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

def _register_sqlite_type_overrides() -> None:
    from sqlalchemy.dialects import sqlite as sqldialect
    from sqlalchemy.dialects.postgresql import INET, JSONB
    sqldialect.base.SQLiteTypeCompiler.visit_INET = lambda self, type_, **kw: "VARCHAR(45)"
    sqldialect.base.SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"
```

### Applies to
T2.x (platform registry), T3.x (graph), T4.x (scan orchestrator), and all future tasks that add new ORM models with PostgreSQL-specific types.

---

## L003 — Use `dict[str, Any]` for external JSON dicts, never `dict[str, object]`

**Date:** 2026-03-21
**Source:** Failure F003 at Task T1.5
**Category:** language
**Tags:** mypy, typing, json, dict, api-response

### Learning
Typing a raw JSON dict as `dict[str, object]` makes `.get()` return `object`. Passing that to `list()`, `int()`, or `str()` fails mypy with `call-overload` or `arg-type` errors. `dict[str, Any]` is correct for external API responses where values have heterogeneous types.

### Rule
Type all external JSON response dicts as `dict[str, Any]`. Reserve `dict[str, object]` only when you want to enforce no implicit narrowing (i.e., you will explicitly cast every value). Always import `Any` explicitly from `typing`.

### Example
```python
# BEFORE (causes mypy call-overload errors on .get() results)
def _parse_breach(raw: dict[str, object]) -> BreachRecord:
    data_classes = list(raw.get("DataClasses", []))  # type: ignore[arg-type]
    pwn_count = int(raw.get("PwnCount", 0))           # type: ignore[arg-type]

# AFTER (correct — Any permits narrowing calls)
from typing import Any
def _parse_breach(raw: dict[str, Any]) -> BreachRecord:
    data_classes = list(raw.get("DataClasses", []))
    pwn_count = int(raw.get("PwnCount", 0))
```

### Applies to
All tasks that parse HTTP API responses: T1.x (HIBP), T2.x (platform APIs), T3.x (graph enrichment).

---

## L004 — Exclude `tests/` from high-entropy string CI scans

**Date:** 2026-03-21
**Source:** Failure F004 at Task T1.5
**Category:** testing
**Tags:** ci, security-scan, secret-detection, regex, false-positive

### Learning
High-entropy string regex patterns (matching `api_key=`, `password=`, etc.) fire false positives on dummy test credentials like `api_key="no-key-needed"`. Test files legitimately need such strings for mock setups and must be excluded from the scan scope.

### Rule
When writing a `git diff | grep` secret scan, always append `':!tests/' ':!*test_*'` to the `git diff` pathspec to exclude test files from the scan.

### Example
```bash
# BEFORE (scans test files, false positive on dummy test API keys)
git diff origin/master...HEAD -- . \
  | grep -E "(api[_-]?key|password)..."

# AFTER (excludes test files)
git diff origin/master...HEAD -- . ':!tests/' ':!*test_*' \
  | grep -E "(api[_-]?key|password)..."
```

### Applies to
Any task that modifies `.github/workflows/security.yml` or adds new secret-scanning steps.

---

## L005 — Set coverage threshold to current project state; raise incrementally

**Date:** 2026-03-21
**Source:** Failure F005 at Task T1.5
**Category:** testing
**Tags:** coverage, pytest, ci, threshold

### Learning
A project-wide coverage threshold set before most modules have tests will block CI as soon as untested boilerplate is added. The threshold must match what the current test suite can achieve, then be raised incrementally as each module gets tested.

### Rule
After adding each new module with tests, update `--cov-fail-under` in both `pyproject.toml` and `.github/workflows/ci.yml` to the highest value the test suite can sustain. Never set it higher than the current measured coverage.

### Example
```toml
# pyproject.toml — raise threshold as modules are tested
# Phase 1 (HIBP only): 50
# Phase 2 (+ platform registry): 60
# Phase 3 (+ graph): 70
# ...
addopts = "--cov-fail-under=50"
```

### Applies to
Every task that adds a new module with unit tests. Check and update threshold at Phase 7 of each task.

---

## L006 — Run `ruff check` on entire project before committing

**Date:** 2026-03-21
**Source:** Failure F006 at Task T1.5
**Category:** language
**Tags:** ruff, linting, imports, isort, ci

### Learning
Ruff's isort (I001) and unused-import (F401) rules are project-wide. An import added in file A may shadow or conflict with imports in file B. Running ruff only on changed files misses these cross-file interactions.

### Rule
Always run `ruff check src/ tests/` and `ruff format src/ tests/` on the **entire project** before committing — not just on the files you changed. Use `ruff check --fix` to auto-fix most issues, then review remaining manual fixes.

### Example
```bash
# WRONG — only checks changed files
ruff check src/piea/modules/hibp.py

# CORRECT — checks whole project
ruff check src/ tests/
ruff format src/ tests/
```

### Applies to
Every task. This is a universal pre-commit gate.

---

## L007 — Re-raise httpx errors as domain errors to prevent PII leaking in messages

**Date:** 2026-03-21
**Source:** Task T1.5 (positive — code review finding)
**Category:** security
**Tags:** httpx, error-handling, pii, email, logging

### Learning
`httpx.HTTPStatusError` includes the full request URL in its string representation. If the URL contains a user's email address (as in the HIBP `/breachedaccount/{email}` endpoint), logging or re-raising this exception raw will expose PII.

### Rule
Always catch `httpx.HTTPStatusError` at the API call site and re-raise as a domain error (e.g., `ModuleAPIError`) that omits the URL. Use `from None` or `from exc` depending on whether the traceback is needed.

### Example
```python
# BEFORE (leaks email in error message via URL)
response.raise_for_status()  # HTTPStatusError includes request URL

# AFTER (sanitized — no PII in message)
try:
    response.raise_for_status()
except httpx.HTTPStatusError as exc:
    raise ModuleAPIError("hibp", exc.response.status_code, "Lookup failed") from None
```

### Applies to
T2.x (platform profile APIs), T3.x (enrichment APIs) — any endpoint that embeds user-identifying data in the URL.

---

## L008 — FastAPI DI providers that create connections must be async generators

**Date:** 2026-03-21
**Source:** Task T1.5 (positive — code review finding)
**Category:** framework
**Tags:** fastapi, dependency-injection, resource-management, redis, httpx, connection-leak

### Learning
Plain functions as FastAPI `Depends()` providers create a new resource (Redis connection, HTTP client) per request with no cleanup path. Over time this exhausts connection pools. Providers that open connections must be `async def` generators with `yield` and `finally` for cleanup.

### Rule
Any DI provider that creates a Redis client, HTTP client, database session, or other closeable resource must use `async def ... yield ... finally: await x.close()` pattern.

### Example
```python
# BEFORE (leaks Redis connections — close() never called)
def get_cache_layer() -> CacheLayer:
    return CacheLayer()

# AFTER (correct — cleanup guaranteed)
async def get_cache_layer() -> AsyncGenerator[CacheLayer, None]:
    cache = CacheLayer()
    try:
        yield cache
    finally:
        await cache.close()
```

### Applies to
T2.x (platform clients), T4.x (scan orchestrator), any task adding new DI providers.

---

## L009 — Rate-limit sleep must be in `finally` block to prevent bypass on exception

**Date:** 2026-03-21
**Source:** Task T1.5 (positive — code review finding)
**Category:** security
**Tags:** asyncio, rate-limiting, semaphore, hibp, httpx

### Learning
If an async rate-limit sleep is placed after the request call (not in `finally`), a `TimeoutException` will exit the semaphore without sleeping. The next queued request then fires immediately, violating the rate limit and triggering unexpected 429 responses.

### Rule
Always put the rate-limit sleep inside a `finally` block so it runs regardless of whether the request raised an exception.

### Example
```python
# BEFORE (sleep skipped on TimeoutException — rate limit violated)
async with self._rate_semaphore:
    response = await self._client.get(url)
    await asyncio.sleep(REQUEST_INTERVAL_SECONDS)  # skipped on exception

# AFTER (correct — sleep always runs)
async with self._rate_semaphore:
    try:
        response = await self._client.get(url)
    except httpx.TimeoutException as exc:
        raise ModuleTimeoutError(...) from exc
    finally:
        await asyncio.sleep(REQUEST_INTERVAL_SECONDS)
```

### Applies to
Any future module that calls a rate-limited external API (T2.x platform APIs, T3.x enrichment).

---

## L010 — Extract result aggregation to keep execute() under 20 lines

**Date:** 2026-03-21
**Source:** Task T2.4 (positive — code structure finding)
**Category:** pattern
**Tags:** module-design, execute-pattern, result-aggregation, maintainability

### Learning
When a module's `execute()` method calls a high-level operation that returns many results (e.g., `UsernameChecker.check_all_platforms()` returns 60+ platform results), aggregating those into ModuleFindings inline makes `execute()` unwieldy. Extract the aggregation logic into a dedicated helper method (`_aggregate_results()`) to keep the main flow clear.

### Rule
Any `execute()` method longer than 20 lines should have its core logic extracted into helper methods. The main flow should read like pseudocode: "call API, aggregate results, return finding".

### Example
```python
# BEFORE (execute too long, hard to follow)
async def execute(self, inputs: ScanInputs) -> ModuleResult:
    if not inputs.username:
        return ModuleResult(...)
    results = await self._checker.check_all_platforms(inputs.username)
    findings = []
    for result in results:
        if result.status == CheckStatus.FOUND:
            findings.append(ModuleFinding(...))
        elif result.status == CheckStatus.ERROR:
            # handle error...
    return ModuleResult(findings=findings, ...)

# AFTER (clear separation of concerns)
async def execute(self, inputs: ScanInputs) -> ModuleResult:
    if not inputs.username:
        return ModuleResult(...)
    results = await self._checker.check_all_platforms(inputs.username)
    findings = self._aggregate_results(results)
    return ModuleResult(findings=findings, success=True, ...)

def _aggregate_results(self, results: list[PlatformCheckResult]) -> list[ModuleFinding]:
    findings = []
    for result in results:
        if result.status == CheckStatus.FOUND:
            findings.append(...)
        elif result.status == CheckStatus.ERROR:
            # error handling...
    return findings
```

### Applies to
T2.5, T2.6 (graph crawler), T3.x (search modules), and any future module with complex result processing.

---

## L011 — Use span tracking in regex extraction to avoid overlapping token matches

**Date:** 2026-03-21
**Source:** Task T2.5 (positive — bio parser implementation)
**Category:** pattern
**Tags:** bio-parsing, regex, token-extraction, overlap-avoidance

### Learning
When extracting multiple token types from unstructured text (bio fields), simple regex `finditer()` loops can match overlapping spans. For example, a URL and an email inside the same URL would both match. Use explicit span tracking to skip already-matched ranges and prevent duplicate/overlapping extractions.

### Rule
In any multi-pattern regex extractor, maintain a set of excluded spans (start, end tuples) and skip new matches that overlap with previously matched tokens. This prevents emails/URLs within longer URLs and ensures each character belongs to at most one token.

### Example
```python
# BEFORE (overlapping matches — email inside URL is extracted twice)
def parse(self, text: str) -> list[BioToken]:
    tokens = []
    for pattern_name, regex in self.PATTERNS.items():
        for match in regex.finditer(text):
            tokens.append(BioToken(
                token_type=pattern_name,
                raw_value=match.group(),
                ...
            ))
    return tokens

# AFTER (span-aware — prevents overlaps)
def parse(self, text: str) -> list[BioToken]:
    tokens = []
    excluded_spans = set()

    for pattern_name, regex in self.PATTERNS.items():
        for match in regex.finditer(text):
            span = (match.start(), match.end())
            # Skip if overlaps with existing token
            if any(s <= match.start() < e or s < match.end() <= e
                   for s, e in excluded_spans):
                continue
            excluded_spans.add(span)
            tokens.append(BioToken(...))

    return sorted(tokens, key=lambda t: t.raw_value.index(t.raw_value))
```

### Applies to
T2.5 (BioParser), T3.x (enrichment APIs that parse text), and any future text parsing module that extracts multiple token types from the same field.

---

## L012 — Set SQLAlchemy UUID ids explicitly at construction time for test usability

**Date:** 2026-03-21
**Source:** Task T2.6 (positive — graph crawler implementation)
**Category:** pattern
**Tags:** sqlalchemy, orm, id-generation, uuid, unit-testing, mocking

### Learning
SQLAlchemy applies column-level defaults (like UUID generation) during `session.flush()` or `session.commit()`, not at Python object construction time. In unit tests where you construct objects without hitting a real database, the id attribute remains `None` until a flush occurs. For test assertions or use in foreign key references before persistence, you must explicitly set the UUID at construction: `node = GraphNode(..., id=uuid4())`.

### Rule
When creating SQLAlchemy ORM objects with UUID primary keys:
1. If the id will be used in tests or before persistence: set it explicitly at construction with `id=uuid4()`
2. Never rely on the default UUID generation to occur at object construction time — it only happens at flush
3. Add the `id` parameter to the dataclass field definition so it's part of the public constructor

### Example
```python
# BEFORE (id is None until session.flush() — breaks tests that reference node.id)
from uuid import uuid4
from sqlalchemy import Column, String, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class GraphNode(Base):
    __tablename__ = "graph_nodes"
    id = Column(UUID, primary_key=True, default=uuid4)
    platform = Column(String(100))

# In test:
node = GraphNode(platform="github", identifier="alice")
assert node.id is not None  # FAILS — id is None until flush()

# AFTER (id set explicitly — works in tests and before persistence)
from uuid import uuid4

class GraphNode(Base):
    __tablename__ = "graph_nodes"
    id = Column(UUID, primary_key=True, default=uuid4)
    platform = Column(String(100))

    def __init__(self, platform: str, identifier: str, id: UUID | None = None, **kwargs):
        self.id = id or uuid4()
        self.platform = platform
        self.identifier = identifier
        for key, value in kwargs.items():
            setattr(self, key, value)

# In test:
node = GraphNode(platform="github", identifier="alice")
assert node.id is not None  # PASSES — id is set immediately
parent_node_id = node.id  # Works before any flush/commit

# Or pass id explicitly:
node = GraphNode(platform="github", identifier="alice", id=uuid4())
```

### Applies to
T2.6 (GraphNode, GraphEdge persistence), T3.x (any new tables with UUID PKs), and all future ORM models that need ids accessible before database flush.

---

## L013 — Group module configuration into frozen dataclass to keep __init__ under 3-parameter rule

**Date:** 2026-03-22
**Source:** Task T3.1 (positive — SearchModule implementation)
**Category:** pattern
**Tags:** module-design, dataclass, constructor-params, dependency-injection

### Learning
Modules that need multiple configuration parameters (API keys, engine IDs, max values, timeouts) violate the 3-parameter rule if each is passed separately. Grouping them into a frozen dataclass (`SearchModuleConfig`) allows a single `config` parameter while keeping the constructor clean.

### Rule
When a module init requires more than 3 parameters, create a frozen dataclass to group related config values. Pass the dataclass as a single `config` parameter. This keeps the constructor signature clean and makes configuration testable in isolation.

### Example
```python
# BEFORE (violates 3-param rule)
class SearchModule(BaseModule):
    def __init__(self, api_key: str, search_engine_id: str, max_queries: int, cache: CacheLayer, httpx_client: httpx.AsyncClient):
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        # ...

# AFTER (clean — config grouped)
from dataclasses import dataclass

@dataclass(frozen=True)
class SearchModuleConfig:
    api_key: str
    search_engine_id: str
    max_queries: int = 3

class SearchModule(BaseModule):
    def __init__(self, config: SearchModuleConfig, cache: CacheLayer):
        self.config = config
        self._cache = cache
```

### Applies to
T3.1 (SearchModule), T3.2 (ResultCategorizer), T4.x (risk scoring modules), and any future module with more than 3 init parameters.

---

## L014 — Use removeprefix for domain extraction, not lstrip

**Date:** 2026-03-22
**Source:** Task T3.1 (positive — broker domain matching)
**Category:** pattern
**Tags:** domain-extraction, string-manipulation, text-normalization

### Learning
`str.lstrip("www.")` removes any chars from the set {'w', '.'} from the left, not the prefix "www." as a unit. On "www.google.com", it removes "www." correctly, but on "w.google.com" it also removes the leading "w", breaking the domain. Use `str.removeprefix()` (Python 3.9+) to safely remove a literal prefix.

### Rule
Never use `lstrip()` to remove prefixes from strings. Always use `removeprefix()` for safe, predictable prefix removal. If the target must be compatible with Python < 3.9, use slicing with a conditional check.

### Example
```python
# BEFORE (lstrip removes chars, not prefix — breaks on edge cases)
domain = "w.google.com"
normalized = domain.lstrip("www.")  # Returns ".google.com" (WRONG!)

# AFTER (correct — removes prefix only)
normalized = domain.removeprefix("www.")  # Returns "w.google.com" (correct)

# For Python < 3.9:
normalized = domain[4:] if domain.startswith("www.") else domain
```

### Applies to
T3.1 (domain normalization in broker matching), T3.2+ (any URL/domain parsing module), and general string processing across the codebase.

---

## L015 — Anchor test paths using Path(__file__).parents[N] instead of hardcoded relative paths

**Date:** 2026-03-22
**Source:** Task T3.1 (positive — test config file loading)
**Category:** testing
**Tags:** test-path-anchoring, pathlib, config-loading, relative-paths

### Learning
Tests that load config files using hardcoded relative paths like `Path("config/data_brokers.json")` fail when the test runner's working directory is not the project root. Using `Path(__file__).parents[N]` anchors paths to the test file's location, working regardless of cwd.

### Rule
In any test that loads external files (fixtures, config, data), construct the path using `Path(__file__).parents[N] / "relative/path/to/file"`. This makes tests independent of cwd.

### Example
```python
# BEFORE (fails if cwd != project root)
import json
from pathlib import Path
def test_load_brokers():
    brokers_path = Path("config/data_brokers.json")
    brokers = json.loads(brokers_path.read_text())
    # pytest from tests/ or src/ cwd breaks this

# AFTER (correct — anchored to test file)
def test_load_brokers():
    brokers_path = Path(__file__).parents[2] / "config" / "data_brokers.json"
    brokers = json.loads(brokers_path.read_text())
    # Works from any cwd
```

### Applies to
T3.1 (test_search.py config loading), T2.x (any test loading config/fixtures), and all future tests that depend on external data files.

---

## L016 — Check both full domain and registered domain when matching config entries

**Date:** 2026-03-22
**Source:** Task T3.2 (positive — bug fix during implementation)
**Category:** pattern
**Tags:** domain-matching, subdomain, categorization, url-parsing

### Learning
When matching a URL's domain against a config-driven domain list, extracting only the registered domain (last 2 labels) loses semantically significant subdomains. For example, `news.ycombinator.com` → `ycombinator.com` fails to match a config entry for `news.ycombinator.com`. The fix is a two-pass check: first try the full normalized domain (with `www.` stripped), then fall back to the registered domain.

### Rule
When building domain-matching logic against config-driven lists, always check both the full normalized domain (e.g., `news.ycombinator.com`) and the registered domain (e.g., `ycombinator.com`). Config authors may list either form.

### Example
```python
# BEFORE (loses subdomain — news.ycombinator.com → ycombinator.com, no match)
domain = self._extract_registered_domain(url, display_link)
for rule in rules:
    if domain in rule.domains:
        return match

# AFTER (checks both forms)
full_domain = self._normalize_domain(display_link, url)  # news.ycombinator.com
registered_domain = self._extract_registered_domain(url, display_link)  # ycombinator.com
for rule in rules:
    if full_domain in rule.domains or registered_domain in rule.domains:
        return match
```

### Applies to
T3.2 (ResultCategorizer), T3.x (any future domain-based classification), and any module that matches URLs against curated domain lists.

---

## L017 — Put classification rules in JSON config for extensibility without code changes

**Date:** 2026-03-22
**Source:** Task T3.2 (positive — design decision)
**Category:** pattern
**Tags:** config-driven, json, extensibility, categorization, domain-matching

### Learning
Hardcoding domain lists and keyword patterns in Python source makes adding new domains or categories require a code change, review, and deploy. Moving these rules to a JSON config file (like `config/search_categories.json`) lets operators update classification behavior without touching Python code, following the same pattern established by `config/platforms.json` (T2.1) and `config/data_brokers.json` (T3.1).

### Rule
When building rule-based classifiers or matchers, put all domain lists, keyword patterns, and category definitions in a JSON config file. Load and parse at initialization time. Log warnings for unknown/invalid entries rather than crashing.

### Example
```python
# BEFORE (hardcoded — requires code change to add domain)
SOCIAL_DOMAINS = {"twitter.com", "facebook.com", "reddit.com"}

# AFTER (config-driven — add domains via JSON)
raw = json.loads(config_path.read_text())
for cat_name, cat_config in raw["categories"].items():
    rules.append(_CategoryRule(
        domains=frozenset(cat_config.get("domains", [])),
        ...
    ))
```

### Applies to
T3.2 (search_categories.json), T3.x (future classifiers), T4.x (risk taxonomy), and any module that classifies data against curated rule sets.

---

<!--
TEMPLATE — copy this for each new learning:

## L[ID] — [Short description of what was learned]

**Date:** YYYY-MM-DD  
**Source:** [Failure F[ID] at Task T[X.Y] | Task T[X.Y] (positive) | Skill creation at Task T[X.Y]]  
**Category:** [language | framework | library | pattern | testing | architecture | performance | security]  
**Tags:** [comma-separated: module names, library names, pattern names — used for search]  

### Learning
[What you now know that you didn't know before — 1-3 sentences max]

### Rule
[A concrete, actionable rule. Start with a verb: "Always...", "Never...", "When X, do Y..."]

### Example
```python
# BEFORE (what caused the issue or was suboptimal)
[code]

# AFTER (the correct or improved approach)
[code]
```

### Applies to
[Which future tasks, modules, or patterns should reference this learning]
[List specific task IDs from PROJECT_PLAN.md if known]
-->

---

## Learnings by category

### Language patterns
- L003: Use `dict[str, Any]` for external JSON dicts
- L006: Run `ruff check` on entire project before committing

### Framework patterns
- L008: FastAPI DI providers that create connections must be async generators

### Library usage
- L001: TruffleHog Action adds `--fail` automatically
- L002: Conftest must prioritize `DATABASE_URL` env var over SQLite fallback

### Design patterns
- L009: Rate-limit sleep must be in `finally` block
- L010: Extract result aggregation to keep execute() under 20 lines
- L011: Use span tracking in regex extraction to avoid overlapping token matches
- L012: Set SQLAlchemy UUID ids explicitly at construction for test usability
- L013: Group module configuration into frozen dataclass to keep __init__ under 3-parameter rule
- L014: Use removeprefix for domain extraction, not lstrip
- L016: Check both full domain and registered domain when matching config entries
- L017: Put classification rules in JSON config for extensibility

### Testing techniques
- L004: Exclude `tests/` from high-entropy string CI scans
- L005: Set coverage threshold to current project state; raise incrementally
- L002: SQLite needs explicit type overrides for PostgreSQL types
- L015: Anchor test paths using Path(__file__).parents[N]

### Architecture decisions
(None yet)

### Performance insights
(None yet)

### Security considerations
- L007: Re-raise httpx errors as domain errors to prevent PII leaking
- L009: Rate-limit sleep in `finally` prevents 429 bypass

---

## Proven patterns registry

**Patterns that have been used successfully and should be reused in similar contexts.**

| Pattern | First used at | Times reused | Skill file |
|---------|-------------|-------------|-----------|
| `async def get_X() -> AsyncGenerator[X, None]: yield; finally: close()` DI provider | T1.5 | 0 | — |
| `except httpx.HTTPStatusError: raise ModuleAPIError(...) from None` | T1.5 | 1 | T3.1 search.py |
| `DATABASE_URL` env var priority in conftest with SQLite type overrides | T1.5 | 0 | — |
| `execute()` calls API, delegates aggregation to `_aggregate_results()`, returns ModuleResult | T2.4 | 1 | T3.1 search.py |
| BFS via `asyncio.Queue` with visited set, `asyncio.wait_for()` for timeout, explicit id=uuid4() | T2.6 | 0 | — |
| `@dataclass(frozen=True) ConfigClass` as single module init param (L013 pattern) | T3.1 | 0 | — |
| Domain normalization: `.lower().removeprefix("www.")` for case-insensitive matching (L014 pattern) | T3.1 | 1 | T3.2 categorizer.py |
| Test path anchoring: `Path(__file__).parents[N] / "relative/path"` for config loading (L015 pattern) | T3.1 | 1 | T3.2 test_result_categorizer.py |
| Two-pass domain check: full domain then registered domain for config matching (L016 pattern) | T3.2 | 0 | — |
| Config-driven classifier: domain/keyword rules in JSON, parsed at init (L017 pattern) | T3.2 | 0 | — |

---

## Anti-patterns registry

**Patterns that have caused failures and must be avoided.**

| Anti-pattern | Discovered at | Failure ID | Prevention rule |
|-------------|-------------|-----------|----------------|
| `extra_args: --only-verified --fail` in TruffleHog Action | T1.5 | F001 | Never pass `--fail` in `extra_args` |
| `sqlite+aiosqlite:///:memory:` conftest without checking `DATABASE_URL` | T1.5 | F002 | Check env var first |
| `dict[str, object]` for external JSON dicts | T1.5 | F003 | Use `dict[str, Any]` |
| High-entropy scan regex without `':!tests/'` exclusion | T1.5 | F004 | Always exclude test paths |
| Project-wide coverage threshold set before most modules have tests | T1.5 | F005 | Match threshold to current state |
| Running `ruff check` only on changed files | T1.5 | F006 | Always run on entire project |
| Rate-limit sleep after request (not in `finally`) | T1.5 | — | Use `finally` block |
| `def get_X() -> X: return X()` plain function DI provider for connections | T1.5 | — | Use async generator |
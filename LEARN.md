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

### Testing techniques
- L004: Exclude `tests/` from high-entropy string CI scans
- L005: Set coverage threshold to current project state; raise incrementally
- L002: SQLite needs explicit type overrides for PostgreSQL types

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
| `except httpx.HTTPStatusError: raise ModuleAPIError(...) from None` | T1.5 | 0 | — |
| `DATABASE_URL` env var priority in conftest with SQLite type overrides | T1.5 | 0 | — |

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
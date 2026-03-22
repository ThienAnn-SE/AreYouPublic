# CLAUDE.md — PIEA Project Context

**Project:** Public Information Exposure Analyzer (PIEA)
**Repo:** ThienAnn-SE/AreYouPublic | **Branch:** master
**Stack:** Python 3.11 · FastAPI · SQLAlchemy (async) · PostgreSQL · Redis · Celery

---

## Iron-clad rules

1. **Never assume. Always verify. Always ask.** If a spec is ambiguous → stop and present a `⛔ BLOCKED` message before writing any code.
2. **Every task follows the 7-phase process** defined in `PROCESS.md`. No phase may be skipped.
3. **Before any task** read: `PROJECT_STATE.md` (current state), `FAIL.md` (failures to avoid), `LEARN.md` (proven patterns).
4. **Before writing code** read: `CODING_RULES.md` (naming, functions, forbidden patterns) once per session.
5. **Phase 5S is mandatory** — run security verification per `SECURITY_WORKFLOW.md` before every commit.
6. **Use the Claude Code skills plugin** — at PROCESS.md Phase 3 Step 3.0, invoke the `Skill` tool to check the plugin catalog before any implementation. Skills provide workflow discipline that overrides default behavior. If any skill has a 1% chance of applying → invoke it. See `PROCESS.md Phase 3 Step 3.0` for the full lookup table.

---

## Critical established patterns (from LEARN.md)

- **L001** — Never pass `--fail` or `--no-update` in TruffleHog Action `extra_args` (it adds them automatically).
- **L002** — `conftest.py` must check `DATABASE_URL` env var first; SQLite needs explicit type overrides for INET/JSONB.
- **L003** — Use `dict[str, Any]` for external JSON; `dict[str, object]` breaks `.get()` calls under mypy.
- **L004** — Exclude `tests/` from high-entropy string scans — test fixtures need dummy credentials.
- **L006** — Run `ruff check src/ tests/` on the ENTIRE project before commit, not just changed files.
- **L007** — Catch `httpx.HTTPStatusError` and re-raise as domain error to prevent PII leaking in messages.
- **L008** — FastAPI DI providers must be async generators with `finally` for resource cleanup.
- **L009** — Rate-limit sleep must be in `finally` block inside semaphore context to prevent bypass on exception.

---

## Quality gates (run in this order per file)

```bash
python -m ruff check src/ tests/
python -m ruff format src/ tests/
python -m mypy src/
python -m pytest tests/ -v --tb=short
```

---

## Mandatory subagent delegation

These are **required gates**, not suggestions. Skipping any delegation is a process violation.

| When | Invoke | What it does |
|------|--------|--------------|
| Start of every task (before writing any code) | `@agent-process-executor` | Runs Phases 1-4 in isolation; returns a ready-to-implement plan |
| Phase 3 Step 3.0 (before implementation code) | `Skill` tool — see lookup table in PROCESS.md Phase 3 Step 3.0 | Check plugin catalog; invoke brainstorming / TDD / writing-plans as applicable |
| After every file written in Phase 5 | `@agent-code-reviewer` | Haiku-model review against CODING_RULES.md; Critical findings must be fixed |
| After Phase 5, before Phase 6 | `@agent-security-auditor` | Runs all 6 Phase 5S security gates; must return PASS ✓ |
| Phase 7 state update (after tests pass) | `@agent-state-updater` | Updates PROJECT_STATE.md, FAIL.md, LEARN.md; names the next task |

**Why delegation is mandatory:** Each agent runs in its own context window. Verbose output (review reports, security scan results, state file diffs) stays inside the agent and only a concise summary returns. This prevents the main conversation from filling up with noise that consumes tokens on every subsequent turn.

---

## Key reference files

| File | Purpose |
|------|---------|
| `PROJECT_PLAN.md` | Architecture, tech stack, phase breakdown |
| `SRS.md` | FR-* and NFR-* requirements |
| `CODING_RULES.md` | Naming conventions, function rules, forbidden patterns |
| `PROCESS.md` | 7-phase execution procedure |
| `PROJECT_STATE.md` | Living file hierarchy, task tracker, established interfaces |
| `FAIL.md` | Failure log — check before every task |
| `LEARN.md` | Accumulated patterns — apply before implementing |
| `SECURITY_WORKFLOW.md` | Security gates and threat model |

# PROCESS.md — Internal Self-Execution Standard Operating Procedure

**Version:** 1.0  
**Purpose:** This document defines the mandatory step-by-step process Claude Code must follow for every task. It is not a guideline — it is the execution engine. Every step must be performed in order. No step may be skipped.  
**Companion files:**
- `FAIL.md` — Failure log with root cause analysis (created on first failure)
- `LEARN.md` — Accumulated learnings and patterns (created on first learning)
- `skills/` — Directory of task-specific skill documents (created as needed)

---

## Process overview

```
For EVERY task, execute these 8 phases in order:

  PHASE 1: REQUIREMENT ANALYSIS
      ↓
  PHASE 2: DEPENDENCY MAPPING
      ↓
  PHASE 3: SKILL ASSESSMENT
      ↓  (if skill gap found → PHASE 3B: SKILL CREATION)
      ↓
  PHASE 4: PRE-IMPLEMENTATION CHECKLIST
      ↓
  PHASE 5: IMPLEMENTATION
      ↓
  PHASE 5S: SECURITY VERIFICATION  ← MANDATORY — see SECURITY_WORKFLOW.md
      ↓  (if secrets/PII found → FIX before proceeding)
      ↓
  PHASE 6: TESTING AND VALIDATION
      ↓  (if test fails → PHASE 6B: FAILURE ANALYSIS → loop back to PHASE 5)
      ↓
  PHASE 7: COMPLETION AND STATE UPDATE
```

---

## PHASE 1: REQUIREMENT ANALYSIS

**Goal:** Understand exactly what the task requires before touching any code.

### Step 1.1 — Identify the task

```
Read PROJECT_STATE.md Section 3.2 to determine the current task.
Record:
  TASK ID:          [from PROJECT_PLAN.md]
  TASK DESCRIPTION: [from PROJECT_PLAN.md]
  PHASE:            [current phase number]
  DELIVERABLE:      [what file(s) or capability this task produces]
```

### Step 1.2 — Extract requirements from SRS.md

For the current task, find every requirement (FR-* and NFR-*) it must satisfy.

```
For each requirement found:
  REQUIREMENT ID:     [e.g., FR-2.1]
  REQUIREMENT TITLE:  [e.g., Email breach lookup]
  ACCEPTANCE CRITERIA: [list every criterion — these become your test cases]
  DATA TYPES:         [exact field names, types, constraints mentioned]
  ERROR CASES:        [what error scenarios are specified]
  EDGE CASES:         [what boundary conditions are implied]
```

**No-assumption checkpoint:** For each requirement, ask yourself:

- Is every input type explicitly specified? If NO → add to questions list.
- Is every output type explicitly specified? If NO → add to questions list.
- Is every error case explicitly specified? If NO → add to questions list.
- Is the behavior for empty/null inputs specified? If NO → add to questions list.
- Are performance constraints specified? If NO → check NFR-P* requirements.

**If the questions list is non-empty → STOP and ask the user before proceeding.**

### Step 1.3 — Check LEARN.md for relevant past learnings

```
Read LEARN.md (if it exists).
Search for entries tagged with:
  - The current task's module name (e.g., "hibp", "graph_crawler")
  - The current task's technology (e.g., "httpx", "sqlalchemy", "fastapi")
  - The current task's pattern type (e.g., "async", "testing", "caching")

If relevant learnings exist:
  Log: "Applying learning L[ID]: [description]"
  Incorporate the learning into your implementation plan.

If LEARN.md does not exist:
  This is fine — it will be created on the first learning event.
```

### Step 1.4 — Check FAIL.md for related past failures

```
Read FAIL.md (if it exists).
Search for entries related to:
  - The same module or file being modified
  - The same library or API being used
  - The same pattern being implemented

If related failures exist:
  Log: "Avoiding known failure F[ID]: [description]"
  Ensure your implementation explicitly avoids the root cause.

If FAIL.md does not exist:
  This is fine — it will be created on the first failure event.
```

---

## PHASE 2: DEPENDENCY MAPPING

**Goal:** Identify everything this task depends on and everything that will depend on this task.

### Step 2.1 — Upstream dependencies (what must exist before this task)

```
Check PROJECT_STATE.md Section 4 (interfaces) and Section 12 (cross-task deps).

For each dependency:
  DEPENDS ON:        [Task ID]
  WHAT IT PROVIDES:  [class name, function, model, table]
  FILE:              [exact file path]
  STATUS:            [created / not created]
  VERIFIED:          [Yes — I confirmed the file exists and contains the expected interface]
                     [No — STOP: dependency not met, cannot proceed]
```

**If any upstream dependency is not met → STOP and report the missing dependency to the user.**

### Step 2.2 — Downstream dependents (what will use this task's output)

```
Check PROJECT_PLAN.md for future tasks that reference this task's deliverable.

For each dependent:
  NEEDED BY:         [Task ID]
  WHAT IT NEEDS:     [class name, function, interface]
  CONSTRAINT:        [any specific interface requirement]
```

**This determines what contracts you must establish.** If future tasks need specific method signatures or field names, build to those contracts now.

### Step 2.3 — File dependencies (what files to import from)

```
Check PROJECT_STATE.md Section 6 (import map).

For each file this task needs to import from:
  FILE:              [path]
  IMPORTS NEEDED:    [specific classes, functions, types]
  VERIFIED EXISTS:   [Yes / No]
  VERIFIED EXPORTS:  [Yes — I confirmed the file exports what I need]
```

**If an import target doesn't exist → STOP. Either the dependency task hasn't been completed, or there's a planning gap. Report to the user.**

### Step 2.4 — Technology dependencies (what libraries/tools are needed)

```
For each external library this task uses:
  LIBRARY:           [name]
  INSTALLED:         [Yes / No — check with: pip show <name> or npm list <name>]
  VERSION:           [installed version]
  REQUIRED BY:       [which part of the task]
  APPROVED:          [Yes — listed in PROJECT_PLAN.md Section 11]
                     [No — STOP and ask user for approval]
```

**If a library is not installed → install it per Rule 7 (auto-install approved deps).**
**If a library is not in the approved list → STOP and ask the user.**

---

## PHASE 3: SKILL ASSESSMENT

**Goal:** Determine whether you have sufficient knowledge/patterns to implement this task correctly on the first attempt.

### Step 3.1 — Identify required skills

For the current task, list every technical skill required:

```
SKILL CHECKLIST:
  [ ] Language pattern:    [e.g., async generators, context managers, dataclass inheritance]
  [ ] Framework pattern:   [e.g., FastAPI dependency injection, SQLAlchemy relationship loading]
  [ ] Library API:         [e.g., httpx retry pattern, dnspython async resolver]
  [ ] Design pattern:      [e.g., strategy pattern for extractors, observer for progress]
  [ ] Algorithm:           [e.g., BFS graph traversal, token bucket rate limiting]
  [ ] Data format:         [e.g., WHOIS response parsing, DNS TXT record format]
  [ ] Testing technique:   [e.g., mocking async context managers, testing Celery tasks]
  [ ] Integration pattern: [e.g., Redis caching with TTL, PostgreSQL JSONB queries]
```

### Step 3.2 — Check existing skills

```
Check if a skill document exists in skills/ directory for each required skill.

For each skill:
  SKILL:             [name]
  SKILL FILE:        [skills/<name>.md or "not found"]
  CONFIDENCE:        [HIGH — I have a proven pattern from CODING_RULES.md or skills/]
                     [MEDIUM — I know the concept but don't have a project-specific template]
                     [LOW — I'm not confident I can implement this correctly first try]
```

### Step 3.3 — Decision gate

```
If ALL skills are HIGH confidence:
  → Proceed to PHASE 4

If ANY skill is MEDIUM confidence:
  → Check CODING_RULES.md Part 3 (API references) and Part 4 (framework patterns)
  → If the pattern is covered there → upgrade to HIGH and proceed
  → If not covered → proceed to PHASE 3B to create the skill

If ANY skill is LOW confidence:
  → MUST proceed to PHASE 3B before implementing
```

---

## PHASE 3B: SKILL CREATION

**Goal:** When a required skill doesn't have a documented pattern, create one before implementation. This prevents trial-and-error coding.**

### Step 3B.1 — Research the skill

```
1. Check CODING_RULES.md Part 3 for the relevant library's official docs URL
2. Check LEARN.md for any related patterns from past tasks
3. Check FAIL.md for failed attempts at similar patterns
4. Identify the BEST PRACTICE approach:
   - What does the library's official documentation recommend?
   - What is the idiomatic pattern for this library version?
   - What error cases does the documentation warn about?
   - What are the performance implications?
```

### Step 3B.2 — Create the skill document

Create a file in `skills/` directory with the following template:

```markdown
# Skill: [Skill Name]

**Created at:** Task [ID]
**Library:** [library name and version]
**Applies to:** [which modules/files will use this skill]

## Problem
[What problem does this skill solve? 1-2 sentences.]

## Best practice pattern
[The recommended implementation pattern with complete, runnable code.]

## Code template
```python
# Copy-paste ready template
# All imports included
# All type annotations included
# Error handling included

[complete code template]
```

## Anti-patterns (what NOT to do)
- [Anti-pattern 1]: [why it's wrong]
- [Anti-pattern 2]: [why it's wrong]

## Error handling
- [Error case 1]: [how to handle]
- [Error case 2]: [how to handle]

## Testing pattern
```python
# How to test this pattern
[test code template]
```

## References
- [Official docs URL]
- [Specific page that documents this pattern]
```

### Step 3B.3 — Verify the skill

```
Before using the skill:
  1. Does the code template pass a mental type-check? (All types consistent)
  2. Does it handle all error cases identified in Phase 1?
  3. Does it conform to CODING_RULES.md? (No forbidden patterns)
  4. Is the test template complete enough to catch regressions?

If any answer is NO → revise the skill document before proceeding.
```

### Step 3B.4 — Log the skill creation

```
Update PROJECT_STATE.md Section 5 (decisions):
  "Created skill document skills/[name].md for [description]"

Update LEARN.md:
  Add entry: "Created reusable pattern for [skill] — see skills/[name].md"
```

---

## PHASE 4: PRE-IMPLEMENTATION CHECKLIST

**Goal:** Final verification before writing code. This is the last gate before implementation.**

### Step 4.1 — Verify you are ready

Answer every question. If any answer is NO, resolve it before proceeding.

```
READINESS CHECKLIST:
  [ ] I have read PROJECT_STATE.md and verified it matches the filesystem
  [ ] I have identified all requirements (FR-*, NFR-*) for this task
  [ ] I have checked LEARN.md for relevant past learnings
  [ ] I have checked FAIL.md for related past failures
  [ ] All upstream dependencies are met and verified
  [ ] All required libraries are installed
  [ ] All required skills are at HIGH confidence (or skill documents created)
  [ ] I know the exact file path for every file I will create or modify
  [ ] I know the exact class names and function names I will use
  [ ] I have verified these names don't conflict with PROJECT_STATE.md Section 11
  [ ] I know what tests I will write (derived from acceptance criteria)
  [ ] I have no unanswered questions — if I do, I must ASK THE USER NOW
```

### Step 4.2 — Write the implementation plan

Before writing code, write a brief plan:

```
IMPLEMENTATION PLAN FOR TASK [ID]:

Files to create:
  1. [path] — [purpose, ~lines estimate]
  2. [path] — [purpose, ~lines estimate]

Files to modify:
  1. [path] — [what changes and why]

Classes/functions to implement:
  1. [ClassName.method_name] — [what it does]
  2. [function_name] — [what it does]

Tests to write:
  1. [test_description] — verifies [acceptance criterion ID]
  2. [test_description] — verifies [acceptance criterion ID]

Skills referenced:
  1. [CODING_RULES.md Part 4.X] or [skills/name.md]

Known risks:
  1. [risk — mitigation]
```

---

## PHASE 5: IMPLEMENTATION

**Goal:** Write the code following the plan, coding rules, and established patterns.

### Step 5.1 — Create files in order

```
Order of creation:
  1. Exception classes (if any new ones needed)
  2. Data models (dataclasses, Pydantic models)
  3. Core logic (the main class/functions for this task)
  4. Integration points (how this connects to existing code)
  5. Configuration (any new settings)
```

### Step 5.2 — For each file, follow this micro-process

```
BEFORE writing the file:
  1. Check CODING_RULES.md Part 5 — file template
  2. Check skills/ for any relevant skill document
  3. Check PROJECT_STATE.md Section 4 for interfaces to conform to
  4. Check PROJECT_STATE.md Section 11 for names already in use

WHILE writing the file:
  1. Follow the file template (module docstring, imports, logger, constants, exceptions, models, main class)
  2. Every function: max 20 lines, max 4 params, type annotations, docstring
  3. Every error path: specific exception, context in message, proper chaining
  4. Every name: check CODING_RULES.md Part 1.1 naming table

AFTER writing the file:
  1. Run: ruff check [file] — fix any issues
  2. Run: ruff format [file] — apply formatting
  3. Run: mypy [file] --strict — fix any type errors
  4. Self-review: read the file as if you didn't write it — is it clear?
```

### Step 5.3 — Run per-file quality gates

```bash
# Execute after EVERY file creation/modification:
ruff check src/piea/[module]/[file].py
ruff format src/piea/[module]/[file].py
mypy src/piea/[module]/[file].py --strict

# If ANY gate fails:
#   1. Fix the issue
#   2. Re-run the gate
#   3. Do NOT proceed to the next file until all gates pass
```

---

## PHASE 5S: SECURITY VERIFICATION

**Goal:** Verify that no secrets, credentials, or real PII have been introduced in the implementation. This phase is MANDATORY and must not be skipped. See `SECURITY_WORKFLOW.md` for the full security policy.

### Step 5S.1 — Scan for secrets in new/modified files

```
For every file created or modified in Phase 5:

  1. Search for hardcoded API keys, passwords, tokens, or credentials
     Pattern: (api_key|secret|password|token|credential)\s*[:=]\s*["'][^"']{8,}
     NOTE: Exclude test files from this scan — they legitimately contain dummy
     credentials. Run on src/ only, or use ':!tests/' ':!*test_*' in git pathspec.

  2. Search for private key material
     Pattern: -----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----

  3. Verify no .env files are staged
     Command: git diff --cached --name-only | grep -E '^\.env'

  If ANY secret is found:
    → REMOVE the secret immediately
    → Replace with environment variable reference or empty default
    → Re-run the scan
    → Do NOT proceed to Phase 6 until clean
```

### Step 5S.2 — Scan for PII in source code and test data

```
For every file created or modified in Phase 5:

  1. Search for real email addresses (excluding RFC 2606 reserved domains)
     Allowed: @example.com, @example.org, @example.net, @test.com
     Blocked: Any other domain in source code or test fixtures

  2. Search for real names (developer names, real person names)
     Allowed: "Test User", "Alice Scanner", "Bob Target", "Jane Operator"
     Blocked: Any real person's name

  3. Search for non-documentation IP addresses in source code
     Allowed: 127.0.0.1, 192.0.2.x, 198.51.100.x, 203.0.113.x
     Blocked: Real IPs in non-config Python files

  4. Verify test fixtures use synthetic data
     Check: All JSON fixtures must contain "_synthetic": true
     Check: All identifiers must match SECURITY_WORKFLOW.md Section 5.1

  If ANY real PII is found:
    → Replace with synthetic equivalent from SECURITY_WORKFLOW.md Section 5.1
    → Re-run the scan
    → Do NOT proceed to Phase 6 until clean
```

### Step 5S.3 — Verify error handling does not leak PII

```
For every new exception handler or log statement in Phase 5:

  1. Error messages must NOT include raw PII values
     WRONG: f"User {email} not found"
     RIGHT: f"User with email hash {hash_email(email)[:8]}... not found"

  2. Log statements at INFO level or below must NOT include raw PII
     WRONG: logger.info(f"Scanning target: {target_name}")
     RIGHT: logger.info(f"Scanning target: {input_name_hash[:8]}...")

  3. API error responses must NOT include stack traces in production
     Verify: FastAPI debug mode is disabled for non-development environments
```

### Step 5S.4 — Security verification result

```
SECURITY VERIFICATION:
  Secrets scan:          [PASS / FAIL — details]
  PII scan:              [PASS / FAIL — details]
  Error handling review: [PASS / FAIL — details]

  If ALL pass: → Proceed to Phase 6
  If ANY fail: → Fix and re-scan before proceeding
```

---

## PHASE 6: TESTING AND VALIDATION

**Goal:** Prove the implementation satisfies every acceptance criterion.

### Step 6.1 — Write tests

```
For each acceptance criterion from Phase 1:
  Create a test that DIRECTLY verifies that criterion.
  
  Test naming: test_[behavior_in_plain_english]
  
  Test structure:
    1. ARRANGE — set up inputs, mocks, fixtures
    2. ACT — call the function/endpoint under test
    3. ASSERT — verify the expected outcome
    
  Test coverage must include:
    - Happy path (normal successful operation)
    - Error paths (every error case from the SRS)
    - Edge cases (empty input, null values, boundary values)
    - Integration points (does it work with upstream dependencies?)
```

### Step 6.2 — Run tests

```bash
# Run tests for this task's files specifically:
pytest tests/unit/test_[module].py -v --tb=long

# Run full test suite to check for regressions:
pytest tests/ -v --tb=short

# Record results:
TESTS RUN:    [count]
TESTS PASSED: [count]
TESTS FAILED: [count]
```

**After adding tests for a new module, update the coverage threshold:**
Check the measured coverage percentage in the pytest output. If it is higher than
the current `--cov-fail-under` in `pyproject.toml` AND `.github/workflows/ci.yml`,
raise the threshold to the new measured value (round down to nearest 5%). Never set
it higher than what the test suite currently achieves.

### Step 6.3 — Decision gate

```
If ALL tests pass:
  → Proceed to PHASE 6.4 (acceptance verification)

If ANY test fails:
  → Proceed to PHASE 6B (failure analysis)
  → Do NOT proceed to Phase 7 until all tests pass
```

### Step 6.4 — Acceptance criteria verification

```
For each acceptance criterion from Phase 1:
  CRITERION: [ID and description]
  TEST:      [test function name that verifies it]
  RESULT:    [PASS / FAIL]
  EVIDENCE:  [what the test output shows]

If ANY criterion is not verified:
  → Write additional test or fix implementation
  → Re-run Phase 6.2
```

---

## PHASE 6B: FAILURE ANALYSIS (Execute on ANY test failure)

**Goal:** Understand WHY a test failed, fix the root cause, and log the learning to prevent recurrence.

### Step 6B.1 — Diagnose the failure

```
For each failing test:

  FAILING TEST:     [test function name]
  ERROR TYPE:       [AssertionError / TypeError / ImportError / TimeoutError / etc.]
  ERROR MESSAGE:    [exact error message]
  STACK TRACE:      [relevant frames]
  
  ROOT CAUSE ANALYSIS:
    WHAT happened:  [describe the failure]
    WHY it happened: [the actual root cause — not the symptom]
    Category:       [one of the categories below]
```

**Failure categories:**

| Category | Description | Example |
|----------|------------|---------|
| LOGIC_ERROR | Algorithm or business logic is wrong | Score calculation produces wrong result |
| TYPE_ERROR | Type mismatch or annotation error | Passed str where int expected |
| INTERFACE_MISMATCH | Code doesn't match established interface | Used wrong field name from upstream model |
| MISSING_HANDLING | Error case not handled | No handler for HTTP 429 response |
| ASYNC_ERROR | Async/await misuse | Forgot to await, event loop conflict |
| MOCK_ERROR | Test mock setup is wrong | Mock returns wrong shape, respx route not matched |
| IMPORT_ERROR | Module import fails | Circular import, missing __init__.py |
| CONFIG_ERROR | Configuration or environment issue | Missing env var, wrong default value |
| RACE_CONDITION | Concurrency timing issue | Semaphore not limiting correctly |
| REGRESSION | Previously passing code now fails | New change broke existing functionality |

### Step 6B.2 — Update FAIL.md

**Create FAIL.md if it doesn't exist. Then append the failure entry.**

```markdown
## F[auto-increment ID] — [Short description]

**Date:** [YYYY-MM-DD]  
**Task:** [Task ID]  
**File:** [file path where the bug was]  
**Test:** [test function name]  
**Category:** [from table above]  

### What happened
[1-2 sentences describing the failure]

### Root cause
[The actual reason — be specific. "The code was wrong" is not a root cause.]

### Fix applied
[What you changed to fix it — be specific]

### Prevention rule
[A concrete rule that would prevent this from happening again]
```

### Step 6B.3 — Update LEARN.md

**Create LEARN.md if it doesn't exist. Then append the learning entry.**

```markdown
## L[auto-increment ID] — [Short description of what was learned]

**Date:** [YYYY-MM-DD]  
**Source:** Failure F[ID] at Task [ID]  
**Category:** [language/framework/library/pattern/testing]  
**Tags:** [comma-separated: module names, library names, pattern names]  

### Learning
[What you now know that you didn't know before — 1-3 sentences]

### Rule
[A concrete, actionable rule. Start with a verb: "Always...", "Never...", "When X, do Y..."]

### Example
```python
# WRONG (what caused the failure)
[code that broke]

# CORRECT (what works)
[code that works]
```

### Applies to
[Which future tasks or modules should reference this learning]
```

### Step 6B.4 — Fix and re-test

```
1. Apply the fix to the source code
2. Run the per-file quality gates (ruff, mypy)
3. Re-run the failing test ONLY: pytest tests/unit/test_[module].py::[TestClass]::[test_name] -v
4. If it passes → run the FULL test suite to check for regressions
5. If it still fails → repeat Phase 6B from Step 6B.1 with the new error
6. Maximum 3 fix attempts per failure. If still failing after 3 attempts:
   → STOP and ask the user for help
   → Include: the test, the error, what you tried, and your current hypothesis
```

### Step 6B.5 — Verify no regressions

```bash
# After fixing any failure, ALWAYS run the full test suite:
pytest tests/ -v --tb=short

# If any previously passing test now fails:
#   This is a REGRESSION — log it in FAIL.md with category REGRESSION
#   Fix the regression before proceeding
#   Do NOT accept a fix that breaks something else
```

---

## PHASE 7: COMPLETION AND STATE UPDATE

**Goal:** Record everything that happened, update all tracking files, prepare for the next task.

### Step 7.1 — Final quality check

```bash
# All five gates must pass:
mypy src/piea/ --strict                    # Zero errors
ruff check src/piea/ tests/                # Zero warnings — ENTIRE project, not just changed files
ruff format --check src/piea/ tests/       # Already formatted — ENTIRE project
pytest tests/ -v --tb=short                # All pass
# Security gate (Phase 5S must have passed — verify no regressions):
# NOTE: Exclude tests/ from secret scan to avoid false positives on dummy test credentials
git diff --cached -- 'src/*.py' '*.json' ':!tests/' | grep -iE '(api_key|secret|password|token)\s*[:=]\s*["'"'"'][^"'"'"']{8,}' && exit 1 || true
```

**Why run ruff on the ENTIRE project?** Import changes in one file (adding `from x import y`) can create `F401 unused import` errors in another file that previously re-exported it. Running on changed files only misses these cross-file interactions.

### Step 7.2 — Update PROJECT_STATE.md

Follow the update instructions in PROJECT_STATE.md exactly. Specifically:

```
Section 2:  Mark all created/modified files with status "created — T[X.Y]"
Section 3:  Update phase tracker, task queue, completed tasks log
Section 4:  Register ALL new:
            - Interfaces (abstract classes, protocols)
            - Data models (dataclasses, Pydantic models) with exact field names and types
            - API endpoints with method, path, request/response models
            - Database tables with column names and types
            - Exception classes with inheritance
Section 5:  Log any technical decisions made during this task
Section 6:  Update import map for all new/modified files
Section 8:  Log any new configuration values
Section 9:  Register any new test fixtures
Section 11: Register ALL new names (classes, functions, models, tables)
Section 12: Log any cross-task dependencies discovered
```

### Step 7.3 — Update PROGRESS.md

```
Add the completed task to the task table.
Update overall progress count.
Update current phase status.
```

### Step 7.4 — Update LEARN.md with positive learnings

**Not just failures — also log what worked well.**

```
If you discovered a particularly effective pattern during this task:
  Add to LEARN.md with source "Task [ID] (positive)"
  
If a skill document proved useful:
  Add to LEARN.md: "Skill [name].md was effective for [use case]"

If a CODING_RULES.md pattern prevented a potential issue:
  Add to LEARN.md: "CODING_RULES.md Part [X] prevented [issue type]"
```

### Step 7.5 — Present completion report

Present the report format defined in CLAUDE_CODE_PROMPT.md Rule 2, Step 5.

### Step 7.6 — Determine next action

```
Check PROJECT_STATE.md Section 3.2 for the next task.

If next task is in the SAME phase:
  → Proceed to Phase 1 for the next task

If next task is in a NEW phase:
  → Present the MILESTONE CHECKPOINT report
  → WAIT for user confirmation before proceeding

If all tasks are complete:
  → Present the FINAL PROJECT REPORT
  → Update PROJECT_STATE.md status to "COMPLETE"
```

---

## SKILL DOCUMENT REGISTRY

**Track all created skill documents here. Update after every Phase 3B.**

```
Status: NO SKILLS CREATED YET

When skills are created:

SKILL: [name]
FILE: skills/[name].md
CREATED AT: Task [ID]
USED BY: [list of tasks that referenced this skill]
EFFECTIVENESS: [HIGH / MEDIUM / LOW — updated after use]
```

---

## PROCESS COMPLIANCE VERIFICATION

**At the start of every task, verify you executed every phase of the previous task:**

```
PREVIOUS TASK COMPLIANCE CHECK:
  [ ] Phase 1 completed — requirements analyzed
  [ ] Phase 2 completed — dependencies mapped
  [ ] Phase 3 completed — skills assessed (3B if needed)
  [ ] Phase 4 completed — pre-implementation checklist passed
  [ ] Phase 5 completed — code written and quality-gated
  [ ] Phase 5S completed — security verification passed (SECURITY_WORKFLOW.md)
  [ ] Phase 6 completed — all tests pass, all criteria verified
  [ ] Phase 6B completed — all failures logged in FAIL.md and LEARN.md (if any failures occurred)
  [ ] Phase 7 completed — PROJECT_STATE.md, PROGRESS.md, LEARN.md updated

If any checkbox is unchecked:
  → Go back and complete it before starting the new task
  → Do NOT carry forward incomplete work
```

---

## EMERGENCY PROCEDURES

### When you're stuck (can't fix a failing test after 3 attempts)

```
1. Log everything you've tried in FAIL.md
2. Log your current hypothesis in FAIL.md
3. Present to the user:
   
   STUCK — REQUESTING ASSISTANCE
   
   Task: [ID]
   Test: [test name]
   Error: [current error]
   
   Attempts made:
     1. [what I tried] → [result]
     2. [what I tried] → [result]
     3. [what I tried] → [result]
   
   Current hypothesis: [what I think might be wrong]
   
   What I need: [specific help requested]
```

### When you discover a requirement gap

```
1. Do NOT guess or assume the missing requirement
2. Log the gap in PROJECT_STATE.md Section 10 (active risks)
3. Present to the user:
   
   REQUIREMENT GAP FOUND
   
   Task: [ID]
   Requirement: [FR-X.Y or area]
   What's missing: [specific detail not specified]
   Why it matters: [what breaks or remains ambiguous without it]
   My suggested default: [what I would do if you approve — or "I have no suggestion"]
   
   Please confirm or provide the missing specification.
```

### When you discover a conflict between documents

```
1. Do NOT resolve the conflict yourself
2. Log it in PROJECT_STATE.md Section 10
3. Present to the user:
   
   DOCUMENT CONFLICT FOUND
   
   Document A: [file, section, what it says]
   Document B: [file, section, what it says]
   Conflict: [how they contradict]
   
   Which document should take precedence for this case?
```
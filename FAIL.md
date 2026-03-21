# FAIL.md — Failure Log and Root Cause Analysis

**Purpose:** Every test failure, build failure, or implementation error is logged here with root cause analysis. Claude Code must check this file before implementing any task to avoid repeating past mistakes.

**How to use:** Before starting Phase 5 (implementation) of any task, search this file for entries matching the current task's module, library, or pattern. Apply the prevention rules from matching entries.

---

## Failure index

| ID | Date | Task | Category | File | Status |
|----|------|------|----------|------|--------|
| (no failures yet) | | | | | |

---

## Failure entries

(No entries yet. First failure will be logged here during Phase 6B of the process.)

<!--
TEMPLATE — copy this for each new failure:

## F[ID] — [Short description]

**Date:** YYYY-MM-DD  
**Task:** T[X.Y]  
**File:** [file path where the bug was]  
**Test:** [test function name that caught it]  
**Category:** [LOGIC_ERROR | TYPE_ERROR | INTERFACE_MISMATCH | MISSING_HANDLING | ASYNC_ERROR | MOCK_ERROR | IMPORT_ERROR | CONFIG_ERROR | RACE_CONDITION | REGRESSION]  
**Status:** FIXED  

### What happened
[1-2 sentences describing the failure symptom]

### Root cause
[The actual underlying reason — be specific]

### Fix applied
[Exact code change or approach that resolved it]

### Prevention rule
[A concrete rule to prevent recurrence. Start with "Always..." or "Never..." or "When X, do Y..."]

### Related
- Similar to: F[other ID] (if applicable)
- Learning created: L[ID]
-->

---

## Statistics

| Category | Count | Last occurrence |
|----------|-------|----------------|
| LOGIC_ERROR | 0 | — |
| TYPE_ERROR | 0 | — |
| INTERFACE_MISMATCH | 0 | — |
| MISSING_HANDLING | 0 | — |
| ASYNC_ERROR | 0 | — |
| MOCK_ERROR | 0 | — |
| IMPORT_ERROR | 0 | — |
| CONFIG_ERROR | 0 | — |
| RACE_CONDITION | 0 | — |
| REGRESSION | 0 | — |

**Update statistics after every new entry.**
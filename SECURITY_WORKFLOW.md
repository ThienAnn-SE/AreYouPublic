# SECURITY_WORKFLOW.md — Sensitive Data Protection Standard

**Version:** 1.0
**Date:** 2026-03-21
**Status:** MANDATORY — This document defines required security gates for every task.
**Companion files:**
- `PROCESS.md` — References this workflow as a required phase
- `.pre-commit-config.yaml` — Automated secret detection hooks
- `.github/workflows/security.yml` — CI secret scanning

---

## 1. Purpose

PIEA handles two categories of sensitive data that must never be exposed in version control, logs, error messages, or CI output:

| Category | Examples | Where it appears |
|----------|---------|-----------------|
| **Infrastructure secrets** | API keys (HIBP, GitHub, Google CSE, Hunter, Reddit), database credentials, Redis URLs, JWT signing keys | `.env`, `config.py` defaults, `docker-compose.yml`, CI environment |
| **Subject PII** | Operator names, operator IPs, target names, target emails, target usernames, scan results, identity graph data | `consent_records`, `scans`, `findings`, `graph_nodes`, `audit_logs`, API request/response bodies, application logs |

This document defines the security gates that prevent accidental exposure at every stage of the development lifecycle.

---

## 2. Threat model — What we are protecting against

| ID | Threat | Impact | Likelihood without controls |
|----|--------|--------|-----------------------------|
| T1 | API key committed to git history | Third-party API abuse, financial cost, account suspension | HIGH — `.env` files, hardcoded strings |
| T2 | Database credentials in git | Full database compromise, PII breach | HIGH — `docker-compose.yml` has defaults |
| T3 | Real PII in test fixtures | Privacy violation, GDPR/PDPD breach | MEDIUM — test data may use real emails |
| T4 | PII leaked in application logs | Privacy violation via log aggregators | MEDIUM — exception messages include field values |
| T5 | Secrets exposed in CI logs | Credential theft from public CI output | MEDIUM — env vars printed in debug output |
| T6 | Sensitive data in error responses | PII exposed to API consumers via stack traces | MEDIUM — FastAPI debug mode, unhandled exceptions |
| T7 | Git author email leaks personal identity | Developer PII exposed in public commit history | LOW — git config email is public in commits |
| T8 | Scan results cached without encryption | PII accessible via Redis without authentication | MEDIUM — Redis default config has no auth |

---

## 3. Security gates — Defense in depth

### 3.1 Gate 1: Pre-commit (developer machine)

**When:** Before every `git commit`
**Tool:** `pre-commit` with `detect-secrets` and custom hooks
**Blocks:** Commits containing secrets or PII patterns

#### What is scanned

| Pattern | Example match | Action |
|---------|--------------|--------|
| High-entropy strings | `sk-proj-abc123...xyz` | BLOCK commit |
| AWS key patterns | `AKIA...` | BLOCK commit |
| Generic API key patterns | `api_key = "real-value"` | BLOCK commit |
| Private key files | `*.pem`, `*.key`, `id_rsa` | BLOCK commit |
| `.env` files (non-example) | `.env`, `.env.local`, `.env.production` | BLOCK commit |
| Email addresses in source | `user@real-domain.com` in `.py`/`.json` | WARN — review needed |
| IP addresses in source | `192.168.1.100` in non-config files | WARN — review needed |
| Hardcoded passwords | `password = "actual_password"` | BLOCK commit |

#### Allowed exceptions (false positives)

| Pattern | Why it's allowed |
|---------|-----------------|
| `.env.example` | Template file with empty/placeholder values |
| `localhost` / `127.0.0.1` | Local development addresses |
| `password` in `docker-compose.yml` | Local dev default (never used in production) |
| `@example.com` / `@test.com` emails | RFC 2606 reserved test domains |
| Test fixture files with synthetic data | Clearly fake data for automated tests |

### 3.2 Gate 2: CI secret scanning (GitHub Actions)

**When:** Every push and pull request
**Tool:** GitHub secret scanning + `trufflehog` in CI
**Blocks:** PR merge if secrets detected in any changed file

#### Workflow triggers

```
Push to any branch → scan changed files
Pull request to master → scan full diff
Schedule (weekly) → scan entire repository history
```

#### What is scanned beyond Gate 1

| Check | Purpose |
|-------|---------|
| Full git history scan (scheduled) | Catch secrets committed and later deleted |
| Binary file analysis | Secrets embedded in compiled files or images |
| GitHub secret scanning alerts | Automatic detection of known provider patterns |
| Dependency vulnerability scan | Known CVEs in project dependencies |

#### TruffleHog Action configuration rules (CRITICAL)

The `trufflesecurity/trufflehog` GitHub Action's internal wrapper script automatically appends `--fail` and `--no-update` to every invocation. **Never pass these flags in `extra_args`** — it will crash with `error: flag 'fail' cannot be repeated`.

```yaml
# CORRECT — only pass scan-behavior flags
- uses: trufflesecurity/trufflehog@main
  with:
    extra_args: --only-verified   # DO NOT add --fail or --no-update here

# WRONG — crashes the job
- uses: trufflesecurity/trufflehog@main
  with:
    extra_args: --only-verified --fail  # duplicate flag error
```

#### High-entropy string scan — test file exclusion (CRITICAL)

When running a `git diff | grep` regex scan for high-entropy strings (pattern: `api[_-]?key|secret|password|token`), always exclude test files. Test code legitimately contains dummy credentials for mock setups.

```bash
# CORRECT — excludes test directories
git diff origin/master...HEAD -- . ':!tests/' ':!*test_*' \
  | grep -iE "(api[_-]?key|secret|password|token)..."

# WRONG — false positives on dummy test API keys like api_key="no-key-needed"
git diff origin/master...HEAD \
  | grep -iE "(api[_-]?key|secret|password|token)..."
```

### 3.3 Gate 3: Code review checklist (human review)

**When:** Every pull request before merge
**Who:** PR author (self-review) or reviewer
**Blocks:** Merge until checklist is confirmed

#### Security review checklist

```
SECURITY REVIEW — Required for every PR

[ ] No real API keys, tokens, or passwords in the diff
[ ] No real email addresses, names, or IP addresses in source code or test data
[ ] Test fixtures use synthetic data only (see Section 5 for approved patterns)
[ ] Error messages do not expose PII (field values, emails, IPs)
[ ] Log statements do not include raw PII (use hashed or redacted forms)
[ ] New environment variables are documented in .env.example (empty values only)
[ ] No new files match .gitignore exclusion patterns (verify intent if adding)
[ ] Database queries do not log raw input values at INFO level or below
[ ] API responses do not include internal identifiers or stack traces
[ ] If adding a new dependency: checked for known vulnerabilities
```

### 3.4 Gate 4: Runtime protections (application code)

**When:** Application execution
**Where:** Source code patterns enforced by code review and linting

#### Required patterns

| Rule | Applies to | Implementation |
|------|-----------|----------------|
| Hash PII before storage | `target_name`, `target_email` | SHA-256 hash in scan creation path (already designed: `input_name_hash`, `input_email_hash` columns) |
| Redact PII in logs | All log statements | Never log raw email, name, or IP at INFO or below; use `***` or hash prefix |
| Sanitize error responses | All API error handlers | Strip stack traces in production; return generic error messages |
| Mask secrets in config repr | `Settings` class | Override `__repr__` to mask API key values |
| Encrypt PII at rest (future) | Database columns with PII | Column-level encryption for `operator_name`, `operator_ip` |
| TTL on cached PII | Redis cache entries | Already designed: `CACHE_TTL_BREACH=86400`, `CACHE_TTL_PROFILE=3600` |

---

## 4. Sensitive data inventory

### 4.1 Infrastructure secrets

| Secret | Source | Storage | Rotation policy |
|--------|--------|---------|----------------|
| `HIBP_API_KEY` | haveibeenpwned.com subscription | `.env` only, GitHub Secrets for CI | Rotate on suspected exposure |
| `GOOGLE_CSE_API_KEY` | Google Cloud Console | `.env` only, GitHub Secrets for CI | Rotate on suspected exposure |
| `GOOGLE_CSE_ENGINE_ID` | Google Programmable Search | `.env` only, GitHub Secrets for CI | Rotate on suspected exposure |
| `GITHUB_TOKEN` | GitHub Developer Settings | `.env` only, GitHub Secrets for CI | Rotate every 90 days |
| `HUNTER_API_KEY` | hunter.io dashboard | `.env` only, GitHub Secrets for CI | Rotate on suspected exposure |
| `REDDIT_CLIENT_ID` | Reddit app settings | `.env` only, GitHub Secrets for CI | Rotate on suspected exposure |
| `REDDIT_CLIENT_SECRET` | Reddit app settings | `.env` only, GitHub Secrets for CI | Rotate on suspected exposure |
| `DATABASE_URL` | Infrastructure config | `.env` only | Change password on exposure |
| `REDIS_URL` | Infrastructure config | `.env` only | Change password on exposure |
| `CELERY_BROKER_URL` | Infrastructure config | `.env` only | Change password on exposure |

### 4.2 PII fields by database table

| Table | Field | PII type | Protection |
|-------|-------|----------|-----------|
| `consent_records` | `operator_name` | Personal name | Stored as-is (audit requirement) |
| `consent_records` | `operator_ip` | IP address | Stored as-is (audit requirement) |
| `scans` | `input_name_hash` | Hashed name | SHA-256 hash (no raw value stored) |
| `scans` | `input_email_hash` | Hashed email | SHA-256 hash (no raw value stored) |
| `scans` | `input_username` | Username | Stored as-is (needed for scan execution) |
| `findings` | `evidence` (JSONB) | May contain PII from API responses | Sanitize before storage |
| `graph_nodes` | `identifier` | Username/email on platform | Stored as-is (needed for graph) |
| `graph_nodes` | `profile_url` | Public profile URL | Stored as-is (public data) |
| `graph_nodes` | `raw_data` (JSONB) | Raw API response | Sanitize — remove non-essential PII |
| `audit_logs` | `operator_ip` | IP address | Stored as-is (audit requirement) |
| `audit_logs` | `event_data` (JSONB) | May contain PII | Sanitize — hash identifiers in event data |

---

## 5. Safe test data standards

### 5.1 Approved synthetic identifiers

All test data MUST use these patterns. Real data is NEVER acceptable.

```
Emails:       testuser@example.com, scan-target@test.com, user{N}@example.org
              (RFC 2606 reserved: example.com, example.org, test.com)

Names:        "Test User", "Alice Scanner", "Bob Target", "Jane Operator"
              (Never use real names, including developer names)

Usernames:    "testuser", "piea_test_account", "fake_user_42"
              (Never use real usernames from any platform)

IPs:          "127.0.0.1", "192.0.2.1", "198.51.100.1", "203.0.113.1"
              (RFC 5737 documentation ranges: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)

Domains:      "example.com", "test.example.org"
              (RFC 2606 reserved domains only)

API keys:     "test-api-key-not-real", "fake-hibp-key-12345"
              (Clearly labeled as fake/test)
```

### 5.2 Test fixture file rules

| Rule | Rationale |
|------|-----------|
| All fixture JSON files must use synthetic data from Section 5.1 | Prevents accidental PII in test data |
| Fixture files must include a `_synthetic: true` field | Machine-readable marker for automated scanning |
| Fixture filenames must not contain real identifiers | `github_profile_testuser.json` not `github_profile_johndoe.json` |
| When recording real API responses for fixture creation, sanitize BEFORE saving | Replace all real identifiers with synthetic ones |

### 5.3 Test fixture sanitization procedure

When creating fixtures from real API responses:

```
1. Make the API call and save the raw response
2. BEFORE committing, replace:
   - All real email addresses → testuser@example.com
   - All real names → "Test User" (or similar)
   - All real usernames → "testuser" (or similar)
   - All real IPs → 192.0.2.1
   - All real URLs → https://example.com/...
   - All real dates → 2020-01-01T00:00:00Z (or clearly synthetic dates)
   - All API keys in responses → "redacted"
3. Add "_synthetic": true to the JSON root
4. Review the entire file manually for any missed PII
5. Only then stage and commit the file
```

---

## 6. Incident response — What to do if secrets are exposed

### 6.1 Secret committed to git

```
SEVERITY: CRITICAL
TIME LIMIT: Act within 15 minutes of discovery

1. ROTATE the exposed credential immediately
   - Go to the provider's dashboard and regenerate the key
   - Update .env with the new key
   - Update GitHub Secrets if applicable

2. REMOVE from git history
   - Use git-filter-repo or BFG Repo-Cleaner to purge the secret
   - Force push the cleaned history (coordinate with team)
   - Verify the secret is gone: grep -r "exposed_value" $(git rev-list --all)

3. AUDIT for abuse
   - Check the provider's API usage logs for unauthorized calls
   - Check application logs for unexpected activity
   - Review GitHub's secret scanning alerts

4. LOG the incident
   - Add entry to FAIL.md with category SECURITY_INCIDENT
   - Record: what was exposed, when, how it was found, impact, remediation
```

### 6.2 PII leaked in logs or error messages

```
SEVERITY: HIGH
TIME LIMIT: Act within 1 hour of discovery

1. IDENTIFY the scope
   - Which logs contain the PII? (application logs, CI logs, monitoring)
   - How long has the PII been exposed?
   - Is the log accessible to unauthorized parties?

2. PURGE the PII
   - Delete or redact the affected log entries
   - If CI logs: delete the workflow run from GitHub Actions
   - If application logs: purge from log aggregator

3. FIX the root cause
   - Update the logging statement to redact PII
   - Add a test that verifies the log output does not contain PII patterns

4. LOG the incident
   - Add entry to FAIL.md with category PII_LEAK
```

---

## 7. Developer security checklist — Quick reference

### Before writing code

```
[ ] I am NOT hardcoding any API keys, passwords, or tokens
[ ] I am NOT using real email addresses, names, or usernames in test data
[ ] My .env file is NOT staged for commit (verify: git status)
```

### Before committing

```
[ ] git diff --cached shows NO secrets or PII
[ ] pre-commit hooks pass (detect-secrets, PII patterns)
[ ] New test fixtures use ONLY synthetic data from Section 5.1
[ ] New environment variables are added to .env.example with EMPTY values
```

### Before creating a PR

```
[ ] Full diff reviewed for secrets and PII (Section 3.3 checklist)
[ ] CI security scan passes
[ ] No .env, .pem, .key, or credentials files in the diff
[ ] Error messages in new code do not expose field values
[ ] Log statements in new code use redacted/hashed PII
```

### Before deploying

```
[ ] All secrets are in environment variables (not in code or config files)
[ ] Database credentials are different from development defaults
[ ] Redis is configured with authentication (not default open)
[ ] Application is NOT running in debug mode
[ ] Error responses return generic messages (no stack traces)
```

---

## 8. File classification

| Classification | Handling | Examples |
|---------------|---------|---------|
| **PUBLIC** | Safe to commit, share, and publish | Source code, README, documentation, test code with synthetic data |
| **INTERNAL** | Safe to commit but review before sharing externally | Architecture docs, process docs, coding rules |
| **CONFIDENTIAL** | NEVER commit to git | `.env`, API keys, database dumps, real scan results |
| **RESTRICTED** | NEVER commit, store, or transmit without encryption | Raw PII, operator personal details, real email/name data |

---

## 9. Compliance mapping

| Security gate | GDPR Article | PDPD (Decree 13/2023) | Requirement |
|--------------|-------------|----------------------|-------------|
| PII hashing before storage | Art. 25 (Data protection by design) | Art. 26 (Security measures) | `input_name_hash`, `input_email_hash` |
| Consent before processing | Art. 6 (Lawful basis) | Art. 11 (Consent) | Consent gate in `core/consent.py` |
| Right to erasure | Art. 17 (Right to erasure) | Art. 16 (Right to delete) | Cascade delete on scan records |
| Audit logging | Art. 30 (Records of processing) | Art. 26 (Security measures) | `audit_logs` table |
| Data minimization | Art. 5(1)(c) (Data minimization) | Art. 3 (Principles) | Hash raw PII, TTL on cache |
| Secret protection | Art. 32 (Security of processing) | Art. 26 (Security measures) | All 4 security gates |

---

## Version history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-21 | Initial version — 4 security gates, threat model, PII inventory |

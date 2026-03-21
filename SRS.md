# Software Requirements Specification — Public Information Exposure Analyzer (PIEA)

**Version:** 1.0  
**Date:** 2026-03-21  
**Document ID:** PIEA-SRS-001  
**Status:** Approved for Development

---

## 1. Introduction

### 1.1 Purpose

This document defines the complete functional and non-functional requirements for the Public Information Exposure Analyzer (PIEA). It serves as the binding contract between stakeholders and the development team. All implementation decisions must trace back to requirements defined in this document.

### 1.2 Scope

PIEA is a web-based security assessment tool that analyzes an individual's public information exposure across the internet. The system collects data exclusively from legitimate public APIs and publicly accessible sources, aggregates findings into a recursive identity graph, computes a weighted risk score, and delivers an actionable exposure report.

The system targets three user personas:

- **Self-assessors** — individuals checking their own digital exposure
- **Security professionals** — penetration testers conducting authorized assessments
- **Security awareness trainers** — demonstrating real exposure risks to employees

### 1.3 Definitions, acronyms, and abbreviations

| Term | Definition |
|------|-----------|
| HIBP | Have I Been Pwned — a breach notification service |
| OSINT | Open Source Intelligence — intelligence from publicly available sources |
| Identity graph | A network of linked accounts and identifiers belonging to a single entity |
| Seed | The initial input (username, email, or name) used to begin a scan |
| Depth | The number of recursive hops from the original seed in the identity graph |
| Node | A single platform presence (e.g., a GitHub account) in the identity graph |
| Edge | A confirmed or inferred link between two nodes |
| Finding | A discrete piece of information discovered during a scan that has risk implications |
| Risk score | A numeric value (0–100) representing the overall exposure level |
| Consent gate | A mandatory pre-scan step requiring documented authorization |
| Platform registry | A configuration file listing all platforms to check during username enumeration |
| Extractor | A module that retrieves and parses profile data from a specific platform's API |
| Bio parser | A component that extracts cross-platform identifiers from free-text biography fields |
| Entity resolution | The process of determining whether scattered data points refer to the same individual |

### 1.4 References

| ID | Document | Description |
|----|----------|-------------|
| REF-1 | HIBP API v3 Documentation | haveibeenpwned.com/API/v3 |
| REF-2 | GitHub REST API Documentation | docs.github.com/en/rest |
| REF-3 | Mastodon API Documentation | docs.joinmastodon.org/api |
| REF-4 | Google Custom Search JSON API | developers.google.com/custom-search/v1 |
| REF-5 | GDPR Article 6 — Lawful Basis for Processing | gdpr-info.eu/art-6-gdpr |
| REF-6 | Vietnam PDPD (Decree 13/2023) | Government decree on personal data protection |
| REF-7 | OWASP Top 10 2021 | owasp.org/Top10 |

---

## 2. Overall description

### 2.1 Product perspective

PIEA is a standalone web application deployed as a set of Docker containers. It has no dependencies on external enterprise systems. All data source integrations use public APIs with documented rate limits and terms of service.

### 2.2 Product functions (high-level)

```
F1: Consent management
F2: Breach exposure analysis
F3: Username enumeration
F4: Recursive identity graph crawling
F5: Public search footprint analysis
F6: Domain and email intelligence
F7: Paste site monitoring
F8: Risk scoring and classification
F9: Report generation and visualization
F10: Scan audit logging
F11: Identity graph visualization
```

### 2.3 User classes and characteristics

| User class | Technical level | Usage pattern | Access level |
|-----------|----------------|--------------|-------------|
| Self-assessor | Low to medium | Occasional (1–2 scans/month) | Own data only |
| Security professional | High | Frequent (10+ scans/week) | Authorized targets |
| Security trainer | Medium | Demo-oriented (curated examples) | Training scenarios |
| System administrator | High | Configuration, monitoring | Full system access |

### 2.4 Operating environment

| Component | Requirement |
|-----------|------------|
| Server OS | Linux (Ubuntu 22.04+ or Alpine 3.18+) |
| Container runtime | Docker 24+ with Docker Compose v2 |
| Python | 3.11 or later |
| Node.js | 20 LTS or later (frontend build) |
| PostgreSQL | 16 or later |
| Redis | 7 or later |
| Browser (client) | Chrome 120+, Firefox 120+, Safari 17+, Edge 120+ |
| Minimum RAM | 2 GB (4 GB recommended) |
| Minimum disk | 10 GB |
| Network | Outbound HTTPS (443) to all target APIs |

### 2.5 Design and implementation constraints

| Constraint | Rationale |
|-----------|-----------|
| C1: All data sources must be public APIs or publicly accessible records | Legal compliance, platform TOS adherence |
| C2: No browser automation or headless scraping | Anti-scraping policy compliance |
| C3: Every scan must have a consent record before execution | Ethical and legal requirement |
| C4: All API keys must remain server-side | Security (OWASP A01:2021 Broken Access Control) |
| C5: Rate limits must be respected per-platform | Platform TOS compliance, IP ban prevention |
| C6: Graph crawl must have hard depth and node limits | Resource protection, DoS prevention |
| C7: No persistent storage of raw API responses beyond cache TTL | Data minimization principle |
| C8: Scan results must be deletable by the user | GDPR Article 17 right to erasure |

### 2.6 Assumptions and dependencies

| ID | Assumption |
|----|-----------|
| A1 | HIBP API v3 remains available and pricing stable |
| A2 | GitHub, Mastodon, Keybase, GitLab, Gravatar, Reddit APIs remain publicly accessible |
| A3 | Google Custom Search free tier continues at 100 queries/day |
| A4 | Target platforms do not block requests from the deployed server IP |
| A5 | Users provide accurate consent information |
| A6 | The deployment environment has unrestricted outbound HTTPS |

---

## 3. Functional requirements

### 3.1 F1 — Consent management

#### FR-1.1 Consent collection

**Priority:** Critical  
**Description:** Before any scan begins, the system shall collect and record a consent attestation from the operator.

**Acceptance criteria:**

- The system shall display a consent form requiring the operator to attest that they are either scanning their own information or have documented written authorization from the subject
- The consent form shall include a mandatory checkbox that must be checked before the scan button becomes active
- The system shall record: operator IP address, timestamp (UTC), consent text version, and the attestation response
- The system shall not execute any data source queries until a valid consent record exists for the scan

#### FR-1.2 Consent audit trail

**Priority:** Critical  
**Description:** All consent records shall be immutable and retained for the configured retention period.

**Acceptance criteria:**

- Consent records shall be stored in PostgreSQL with a non-nullable `created_at` timestamp
- Consent records shall not be editable or deletable through the application (only via direct database admin access)
- Each scan result shall contain a foreign key reference to its consent record
- The system shall expose an admin endpoint to list all consent records with filters for date range and operator IP

---

### 3.2 F2 — Breach exposure analysis

#### FR-2.1 Email breach lookup

**Priority:** Critical  
**Description:** Given an email address, the system shall query HIBP API v3 to retrieve all known data breaches associated with that address.

**Acceptance criteria:**

- The system shall send a GET request to `https://haveibeenpwned.com/api/v3/breachedaccount/{email}` with the `hibp-api-key` header
- The system shall handle HTTP 200 (breaches found), 404 (no breaches), and 429 (rate limited) responses
- For each breach returned, the system shall extract: breach name, breach date, data classes exposed, description, domain, and whether the breach is verified
- The system shall classify each breach by severity:
  - Critical: password hashes, plaintext passwords, or financial data exposed
  - High: phone numbers, physical addresses, or government IDs exposed
  - Medium: email addresses, usernames, or IP addresses exposed
  - Low: email-only exposure with no sensitive data classes
- The system shall cache breach results in Redis with a 24-hour TTL keyed by SHA-256 hash of the email

#### FR-2.2 Password exposure check

**Priority:** High  
**Description:** Given a password hash prefix, the system shall check whether the password appears in known breach datasets using HIBP's k-anonymity model.

**Acceptance criteria:**

- The system shall accept an optional password field in the scan input
- The password shall be SHA-1 hashed client-side before transmission (never sent in plaintext)
- The system shall send only the first 5 characters of the hash to HIBP's range endpoint
- The system shall match the remaining hash suffix against the returned list
- If a match is found, the system shall report the password as compromised with the occurrence count
- The raw password or full hash shall never be logged, stored, or transmitted to the backend

---

### 3.3 F3 — Username enumeration

#### FR-3.1 Multi-platform existence check

**Priority:** Critical  
**Description:** Given a username, the system shall check whether that username exists as a registered account on every platform defined in the platform registry.

**Acceptance criteria:**

- The platform registry shall be stored as a JSON configuration file with the following schema per entry:
  ```json
  {
    "platform": "github",
    "url_pattern": "https://github.com/{username}",
    "expected_status_found": 200,
    "expected_status_not_found": 404,
    "category": "development",
    "has_public_api": true,
    "rate_limit_requests_per_minute": 60
  }
  ```
- The system shall support a minimum of 300 platforms in the registry
- All platform checks shall execute concurrently using async HTTP requests with a configurable concurrency limit (default: 50 simultaneous connections)
- For each platform, the system shall send an HTTP GET or HEAD request to the URL pattern with the username substituted
- The system shall classify the result as: found (expected success status), not found (expected not-found status), error (timeout, connection failure, unexpected status), or rate-limited (429)
- The system shall complete all existence checks within 30 seconds for a single username
- Results shall be returned as a list of platform matches with: platform name, profile URL, category, and check timestamp

#### FR-3.2 Per-platform rate limiting

**Priority:** High  
**Description:** The system shall enforce per-platform rate limits to prevent IP bans and comply with platform policies.

**Acceptance criteria:**

- Each platform in the registry shall have a `rate_limit_requests_per_minute` field
- The system shall implement a token bucket rate limiter per platform domain
- If a platform returns HTTP 429, the system shall back off exponentially (initial: 5 seconds, max: 60 seconds, 3 retries)
- Rate limiter state shall be stored in Redis to persist across application restarts
- The system shall log all rate limit events with platform name and retry count

---

### 3.4 F4 — Recursive identity graph crawling

#### FR-4.1 Profile data extraction

**Priority:** Critical  
**Description:** For platforms with public APIs (Tier 1), the system shall extract structured profile data including cross-platform links.

**Acceptance criteria:**

The system shall implement dedicated extractors for the following platforms:

**GitHub extractor:**
- Endpoint: `https://api.github.com/users/{username}`
- Shall extract: `login`, `name`, `company`, `blog`, `twitter_username`, `bio`, `email`, `public_repos`, `created_at`
- Shall use GitHub personal access token for authenticated requests (5000/hr limit)

**Mastodon extractor:**
- Endpoint: `https://{instance}/api/v1/accounts/lookup?acct={username}`
- Shall extract: `display_name`, `note` (bio), `fields` (verified links), `url`, `followers_count`, `statuses_count`
- Shall support instance discovery (try common instances: mastodon.social, infosec.exchange, hachyderm.io, fosstodon.org, plus instances discovered from links)
- Shall flag verified fields (rel="me" verified links) with confidence 1.0

**Keybase extractor:**
- Endpoint: `https://keybase.io/_/api/1.0/user/lookup.json?username={username}`
- Shall extract all cryptographic proofs: GitHub, Twitter, Reddit, Hacker News, personal domains
- Shall flag all Keybase-verified proofs with confidence 1.0

**GitLab extractor:**
- Endpoint: `https://gitlab.com/api/v4/users?username={username}`
- Shall extract: `bio`, `website`, `twitter`, `linkedin`, `organization`

**Gravatar extractor:**
- Endpoint: `https://en.gravatar.com/{md5_of_email}.json`
- Shall extract: `displayName`, `urls` array, `accounts` array, `aboutMe`

**Reddit extractor:**
- Endpoint: `https://www.reddit.com/user/{username}/about.json`
- Shall extract: `subreddit.public_description`, `total_karma`, `created_utc`
- Shall set User-Agent header to comply with Reddit API rules

#### FR-4.2 Bio text link parsing

**Priority:** High  
**Description:** The system shall parse free-text biography fields to extract cross-platform identifiers.

**Acceptance criteria:**

- The parser shall extract the following identifier types from any text input:
  - URLs (any `https://` or `http://` link)
  - Twitter/X handles (`@username` format, or `twitter.com/username`)
  - GitHub references (`github.com/username`)
  - LinkedIn profiles (`linkedin.com/in/slug`)
  - Email addresses (RFC 5322 compliant pattern)
  - Mastodon handles (`@user@instance.tld` format)
  - Keybase references (`keybase.io/username`)
  - Personal domain references (any standalone domain mention)
- Each extracted identifier shall be returned with: type (url, handle, email, domain), raw value, normalized value, and the platform it maps to (if identifiable)
- The parser shall handle common text patterns: "find me on X as ...", "also on ...", "website: ...", "blog: ..."
- The parser shall not produce false positives on common English words or generic punctuation

#### FR-4.3 Recursive graph expansion

**Priority:** Critical  
**Description:** The system shall recursively discover and follow cross-platform links to build a complete identity graph.

**Acceptance criteria:**

- The crawl algorithm shall implement breadth-first expansion starting from the seed identifier
- Each discovered cross-platform link shall be added to a work queue for the next depth level
- The system shall enforce the following hard limits:
  - Maximum crawl depth: configurable, default 3
  - Maximum total nodes: configurable, default 500
  - Maximum wall-clock time: configurable, default 120 seconds
- The system shall maintain a visited set to prevent re-checking the same (platform, identifier) pair
- Cycle detection: if an edge would create a cycle (A→B→C→A), the edge shall be recorded but the target shall not be re-crawled
- Each node in the graph shall store:
  - `platform` (string): the platform name
  - `identifier` (string): the username, email, or URL
  - `profile_url` (string): direct link to the profile
  - `confidence` (float, 0.0–1.0): how certain the system is that this belongs to the same person
  - `discovered_at_depth` (int): the crawl depth at which this node was found
  - `raw_data` (dict): the full API response for Tier 1 profiles, empty dict for Tier 2
- Each edge in the graph shall store:
  - `source_node_id` (string): the node that contained the link
  - `target_node_id` (string): the node being linked to
  - `evidence_type` (enum): one of `api_field`, `verified_link`, `bio_mention`, `same_username`, `keybase_proof`
  - `confidence` (float, 0.0–1.0): derived from evidence type

**Confidence scoring rules:**

| Evidence type | Confidence score |
|--------------|-----------------|
| `keybase_proof` — cryptographically verified | 1.0 |
| `verified_link` — Mastodon rel="me" verified | 1.0 |
| `api_field` — structured field (e.g., GitHub `twitter_username`) | 0.9 |
| `bio_mention` — parsed from free text with URL match | 0.7 |
| `bio_mention` — parsed from free text, handle only | 0.5 |
| `same_username` — identical username on different platform | 0.3 |

---

### 3.5 F5 — Public search footprint analysis

#### FR-5.1 Web search query

**Priority:** Medium  
**Description:** The system shall search the public web for mentions of the subject's name and identifiers.

**Acceptance criteria:**

- The system shall construct search queries using combinations of: full name, email address, username, and known associated domains
- The system shall use Google Custom Search JSON API with the configured API key and Search Engine ID
- The system shall execute a maximum of 3 search queries per scan to stay within free tier limits
- For each search result, the system shall extract: title, snippet, URL, and display link
- The system shall categorize each result as: social profile, news mention, professional directory, forum post, data broker listing, or uncategorized
- The system shall implement entity disambiguation: if the subject's name is common (produces 100+ results), the system shall require at least one secondary signal (email, username, employer, location) to match a result to the subject

#### FR-5.2 Data broker detection

**Priority:** Medium  
**Description:** The system shall flag search results that appear on known data broker or people-search websites.

**Acceptance criteria:**

- The system shall maintain a list of known data broker domains (minimum 20: Spokeo, BeenVerified, WhitePages, Pipl, ThatsThem, etc.)
- If a search result URL matches a data broker domain, the finding shall be flagged as high severity
- The finding shall include a remediation recommendation with the data broker's specific opt-out URL where known

---

### 3.6 F6 — Domain and email intelligence

#### FR-6.1 WHOIS lookup

**Priority:** Medium  
**Description:** Given a domain name (from a personal website or email), the system shall retrieve WHOIS registration data.

**Acceptance criteria:**

- The system shall use the `python-whois` library for WHOIS lookups
- The system shall extract: registrant name, registrant organization, registration date, expiration date, registrar, name servers, and whether privacy protection is enabled
- If privacy protection is not enabled and personal information is visible, this shall be flagged as a high-severity finding
- The system shall handle WHOIS lookup failures gracefully (WHOIS server timeout, rate limited, domain not found)

#### FR-6.2 DNS security posture

**Priority:** Medium  
**Description:** The system shall analyze DNS records to assess the email security posture of the subject's domain.

**Acceptance criteria:**

- The system shall query: MX records, TXT records (for SPF), and TXT records at `_dmarc.{domain}` (for DMARC)
- The system shall classify the domain's email security as:
  - Strong: valid SPF + DMARC with `p=reject` or `p=quarantine`
  - Moderate: valid SPF + DMARC with `p=none`
  - Weak: SPF present but no DMARC
  - None: no SPF and no DMARC
- Missing DMARC shall be flagged as a medium-severity finding (domain vulnerable to email spoofing)

---

### 3.7 F7 — Paste site monitoring

#### FR-7.1 Paste exposure check

**Priority:** Low  
**Description:** The system shall check whether the subject's email or username appears in publicly indexed paste sites.

**Acceptance criteria:**

- The system shall check HIBP's paste endpoint: `https://haveibeenpwned.com/api/v3/pasteaccount/{email}`
- For each paste found, the system shall record: paste source (Pastebin, Ghostbin, etc.), paste title, paste date, and email count in paste
- Paste exposure shall be flagged as a high-severity finding (indicates the email was in a credential dump)

---

### 3.8 F8 — Risk scoring and classification

#### FR-8.1 Weighted risk scoring

**Priority:** Critical  
**Description:** The system shall compute a numeric risk score (0–100) from all findings using a configurable weighted algorithm.

**Acceptance criteria:**

- The risk taxonomy shall be defined in `risk_taxonomy.json` with the following structure per finding type:
  ```json
  {
    "finding_type": "breach_password_exposed",
    "category": "credential_exposure",
    "base_weight": 25,
    "max_contribution": 50,
    "stacking": "additive_capped"
  }
  ```
- The scoring algorithm shall:
  1. For each finding, look up the base weight in the taxonomy
  2. Apply stacking rules: `additive_capped` (each occurrence adds base weight up to max_contribution), `flat` (single occurrence adds base weight regardless of count), `diminishing` (each additional occurrence adds 50% of the previous)
  3. Sum all weighted contributions
  4. Normalize to 0–100 scale using: `final_score = min(100, raw_sum)`
- The system shall produce a category-level breakdown showing contribution from each category: credential exposure, platform proliferation, public data exposure, infrastructure weakness, identity correlation risk

**Default weight matrix:**

| Finding type | Base weight | Max contribution | Stacking |
|-------------|-------------|-----------------|---------|
| Password exposed in breach | 25 | 50 | additive_capped |
| Email-only breach | 5 | 15 | additive_capped |
| Username found on platform | 0.5 | 15 | additive_capped |
| Tier 1 profile with extractable links | 3 | 15 | additive_capped |
| Keybase proof chain exists | 5 | 5 | flat |
| Cross-platform username reuse (10+) | 10 | 10 | flat |
| WHOIS data not privacy-protected | 15 | 15 | flat |
| No DMARC on email domain | 8 | 8 | flat |
| No SPF on email domain | 5 | 5 | flat |
| Data broker listing found | 12 | 24 | additive_capped |
| Paste site exposure | 15 | 30 | additive_capped |
| Phone number publicly visible | 12 | 12 | flat |
| Physical address publicly visible | 10 | 10 | flat |
| Graph depth reached 3+ | 5 | 5 | flat |
| Stale account detected (no activity 2+ years) | 3 | 12 | additive_capped |

#### FR-8.2 Risk tier classification

**Priority:** Critical  
**Description:** The system shall classify the final score into a risk tier.

**Acceptance criteria:**

| Score range | Tier | Label | Color |
|------------|------|-------|-------|
| 0–20 | 1 | Low exposure | Green |
| 21–40 | 2 | Moderate exposure | Yellow |
| 41–65 | 3 | High exposure | Orange |
| 66–100 | 4 | Critical exposure | Red |

#### FR-8.3 Remediation recommendations

**Priority:** High  
**Description:** For every finding, the system shall provide a specific, actionable remediation recommendation.

**Acceptance criteria:**

- Each finding type in the taxonomy shall have an associated remediation template
- Remediation templates shall support variable substitution (e.g., "Change your password on {platform_name} and enable MFA")
- Recommendations shall be prioritized by the finding's severity weight
- The report shall group recommendations by effort level: immediate (< 5 minutes), short-term (< 1 hour), long-term (requires planning)

---

### 3.9 F9 — Report generation and visualization

#### FR-9.1 Web report dashboard

**Priority:** High  
**Description:** The system shall render an interactive report in the browser.

**Acceptance criteria:**

- The report shall contain the following sections in order:
  1. Header: subject identifiers used, scan timestamp, scan duration
  2. Risk score gauge: circular gauge showing 0–100 score with tier label and color
  3. Executive summary: 2–3 sentence natural language summary of key findings
  4. Category breakdown: horizontal bar chart showing contribution from each risk category
  5. Identity graph: interactive network visualization of all discovered nodes and edges
  6. Findings list: expandable cards grouped by severity (critical first), each showing finding type, description, affected platform, evidence, and remediation
  7. Remediation roadmap: prioritized action items grouped by effort level
- The report shall be viewable without authentication (accessed via unique scan ID in URL)
- The report URL shall use a UUID that is not guessable

#### FR-9.2 Identity graph visualization

**Priority:** High  
**Description:** The report shall include an interactive network graph of the discovered identity.

**Acceptance criteria:**

- The graph shall render using D3.js force-directed layout
- Nodes shall be colored by platform category (development = blue, social = purple, professional = teal, email = amber, personal site = green)
- Node size shall scale with the number of edges connected to it
- Edges shall be styled by confidence: solid line for >= 0.8, dashed for 0.5–0.8, dotted for < 0.5
- Edge color shall vary by evidence type (green for cryptographic proof, blue for API field, gray for username match)
- Hovering over a node shall display: platform, identifier, confidence score, and discovery depth
- Clicking a node shall open the profile URL in a new tab
- The graph shall support zoom and pan
- The seed node shall be visually distinct (larger, highlighted border)

#### FR-9.3 PDF export

**Priority:** Low  
**Description:** The user shall be able to export the report as a PDF document.

**Acceptance criteria:**

- The PDF shall contain all report sections except the interactive graph (replaced by a static screenshot)
- The PDF shall include a header with scan metadata and a footer with the disclaimer
- The PDF shall be generated server-side and downloadable via a button on the report page

---

### 3.10 F10 — Scan audit logging

#### FR-10.1 Audit log persistence

**Priority:** Critical  
**Description:** Every scan action shall be logged for audit purposes.

**Acceptance criteria:**

- The audit log shall record: scan ID, operator IP, consent record ID, scan start time, scan end time, input parameters (hashed, not raw), modules executed, findings count, risk score, and any errors encountered
- Audit logs shall be stored in PostgreSQL in a dedicated `audit_logs` table
- Audit logs shall not be deletable through the application
- The system shall expose an admin endpoint to query audit logs with filters

---

## 4. Non-functional requirements

### 4.1 Performance

| ID | Requirement | Target |
|----|------------|--------|
| NFR-P1 | Full scan completion time (all modules) | < 120 seconds (95th percentile) |
| NFR-P2 | Username enumeration (300+ platforms) | < 30 seconds |
| NFR-P3 | Report page load time | < 2 seconds |
| NFR-P4 | API response time (submit scan) | < 500ms |
| NFR-P5 | Concurrent scan support | Minimum 5 simultaneous scans |
| NFR-P6 | Identity graph rendering (500 nodes) | < 3 seconds in browser |

### 4.2 Security

| ID | Requirement |
|----|------------|
| NFR-S1 | All API keys shall be stored as environment variables, never in source code or client-side code |
| NFR-S2 | All external API communication shall use HTTPS (TLS 1.2+) |
| NFR-S3 | User-supplied input shall be validated and sanitized against injection attacks (SQL, command, SSRF) |
| NFR-S4 | The system shall not store raw passwords; password checking uses k-anonymity (only 5-char hash prefix transmitted) |
| NFR-S5 | Scan report URLs shall use UUIDv4 (122 bits of entropy), not sequential IDs |
| NFR-S6 | The system shall implement CORS restrictions (only allow configured frontend origin) |
| NFR-S7 | Rate limiting shall be enforced on all public endpoints (10 scans/hour per IP, 100 report views/hour per IP) |
| NFR-S8 | The system shall log all authentication and authorization events |
| NFR-S9 | Docker containers shall run as non-root user |
| NFR-S10 | Dependencies shall be pinned to specific versions and audited for known vulnerabilities monthly |

### 4.3 Reliability

| ID | Requirement |
|----|------------|
| NFR-R1 | If an individual data source module fails (API timeout, rate limit), the scan shall continue with remaining modules and note the failure in the report |
| NFR-R2 | The system shall retry failed API calls up to 3 times with exponential backoff before marking the module as failed |
| NFR-R3 | The graph crawler shall not crash or hang regardless of input; all code paths shall have timeout protection |
| NFR-R4 | Database connection pooling shall handle connection drops gracefully with automatic reconnection |
| NFR-R5 | The system shall provide a health check endpoint that verifies database, Redis, and Celery worker connectivity |

### 4.4 Scalability

| ID | Requirement |
|----|------------|
| NFR-SC1 | The system shall support horizontal scaling of Celery workers for concurrent scan processing |
| NFR-SC2 | The platform registry shall support adding new platforms without code changes (JSON configuration only) |
| NFR-SC3 | New data source modules shall be addable by implementing the base module interface without modifying the orchestrator |
| NFR-SC4 | The risk taxonomy shall be modifiable without code changes (JSON configuration) |

### 4.5 Maintainability

| ID | Requirement |
|----|------------|
| NFR-M1 | All Python code shall pass mypy strict mode type checking |
| NFR-M2 | All Python code shall pass ruff linting with zero warnings |
| NFR-M3 | Test coverage shall be minimum 80% for all modules |
| NFR-M4 | Every public function and class shall have a docstring |
| NFR-M5 | The API shall be documented via auto-generated OpenAPI 3.0 specification |
| NFR-M6 | Database schema changes shall be managed exclusively through Alembic migrations |

### 4.6 Legal and compliance

| ID | Requirement |
|----|------------|
| NFR-L1 | The system shall not access any data that requires authentication to view |
| NFR-L2 | The system shall not violate any platform's Terms of Service (only public API endpoints, no scraping) |
| NFR-L3 | The system shall comply with GDPR data minimization principles: collect only what is needed, cache with TTLs, allow deletion |
| NFR-L4 | The system shall support data deletion requests: a user can request deletion of their scan results and the system shall purge them within 72 hours |
| NFR-L5 | The system shall display a clear disclaimer on every report stating that the tool only accesses publicly available information |
| NFR-L6 | The system shall not provide legal advice or make claims about legality of discovered exposures |

---

## 5. Interface requirements

### 5.1 REST API endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/scans` | Create a new scan | Rate limited |
| GET | `/api/v1/scans/{scan_id}` | Get scan status and progress | None (UUID auth) |
| GET | `/api/v1/scans/{scan_id}/report` | Get completed scan report | None (UUID auth) |
| DELETE | `/api/v1/scans/{scan_id}` | Delete scan and all associated data | Rate limited |
| GET | `/api/v1/health` | System health check | None |
| GET | `/api/v1/platforms` | List supported platforms | None |
| GET | `/api/v1/admin/audit-logs` | Query audit logs | Admin token |

### 5.2 Scan request schema

```json
{
  "inputs": {
    "name": "string | null",
    "email": "string | null",
    "username": "string | null",
    "phone": "string | null"
  },
  "options": {
    "max_depth": "integer (1-5, default 3)",
    "modules": ["hibp", "username_enum", "graph_crawl", "search", "domain_intel", "paste_monitor"],
    "timeout_seconds": "integer (30-300, default 120)"
  },
  "consent": {
    "attestation": "self_assessment | authorized_assessment",
    "operator_name": "string",
    "consent_text_version": "string"
  }
}
```

**Validation rules:**
- At least one input field must be non-null
- If `attestation` is `authorized_assessment`, `operator_name` is required
- `email` must match RFC 5322 pattern if provided
- `username` must be 1–39 characters, alphanumeric with hyphens/underscores
- `phone` must match E.164 format if provided

### 5.3 Scan response schema

```json
{
  "scan_id": "uuid",
  "status": "queued | running | completed | failed | cancelled",
  "progress": {
    "percent": "integer (0-100)",
    "current_module": "string",
    "modules_completed": "integer",
    "modules_total": "integer",
    "nodes_discovered": "integer",
    "findings_count": "integer"
  },
  "created_at": "ISO 8601 timestamp",
  "completed_at": "ISO 8601 timestamp | null",
  "report_url": "string | null"
}
```

### 5.4 Report response schema

```json
{
  "scan_id": "uuid",
  "metadata": {
    "inputs_used": {},
    "scan_duration_seconds": "float",
    "modules_executed": [],
    "modules_failed": [],
    "timestamp": "ISO 8601"
  },
  "risk_score": {
    "total": "integer (0-100)",
    "tier": "low | moderate | high | critical",
    "category_breakdown": {
      "credential_exposure": "integer",
      "platform_proliferation": "integer",
      "public_data_exposure": "integer",
      "infrastructure_weakness": "integer",
      "identity_correlation": "integer"
    }
  },
  "identity_graph": {
    "nodes": [],
    "edges": [],
    "stats": {
      "total_nodes": "integer",
      "total_edges": "integer",
      "max_depth_reached": "integer",
      "platforms_found": "integer"
    }
  },
  "findings": [
    {
      "id": "uuid",
      "type": "string",
      "severity": "critical | high | medium | low",
      "category": "string",
      "title": "string",
      "description": "string",
      "platform": "string | null",
      "evidence": {},
      "remediation": {
        "action": "string",
        "effort": "immediate | short_term | long_term",
        "url": "string | null"
      }
    }
  ],
  "disclaimer": "string"
}
```

---

## 6. Data model

### 6.1 Entity relationship summary

```
scans (1) ──── (1) consent_records
scans (1) ──── (N) findings
scans (1) ──── (N) graph_nodes
scans (1) ──── (N) graph_edges
scans (1) ──── (N) audit_logs
graph_nodes (1) ──── (N) graph_edges (as source)
graph_nodes (1) ──── (N) graph_edges (as target)
```

### 6.2 Table definitions

**consent_records**

| Column | Type | Constraints |
|--------|------|------------|
| id | UUID | PK, default gen_random_uuid() |
| attestation_type | VARCHAR(50) | NOT NULL |
| operator_name | VARCHAR(255) | NOT NULL |
| operator_ip | INET | NOT NULL |
| consent_text_version | VARCHAR(20) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

**scans**

| Column | Type | Constraints |
|--------|------|------------|
| id | UUID | PK, default gen_random_uuid() |
| consent_record_id | UUID | FK → consent_records(id), NOT NULL |
| status | VARCHAR(20) | NOT NULL, default 'queued' |
| input_name_hash | VARCHAR(64) | SHA-256 hash of input name |
| input_email_hash | VARCHAR(64) | SHA-256 hash of input email |
| input_username | VARCHAR(255) | Stored as-is (not sensitive) |
| risk_score | INTEGER | NULL until completed |
| risk_tier | VARCHAR(20) | NULL until completed |
| modules_config | JSONB | Modules and options selected |
| started_at | TIMESTAMPTZ | NULL until running |
| completed_at | TIMESTAMPTZ | NULL until completed |
| error_message | TEXT | NULL unless failed |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

**findings**

| Column | Type | Constraints |
|--------|------|------------|
| id | UUID | PK |
| scan_id | UUID | FK → scans(id), NOT NULL |
| type | VARCHAR(100) | NOT NULL |
| severity | VARCHAR(20) | NOT NULL |
| category | VARCHAR(50) | NOT NULL |
| title | VARCHAR(500) | NOT NULL |
| description | TEXT | NOT NULL |
| platform | VARCHAR(100) | NULL |
| evidence | JSONB | NOT NULL |
| weight_applied | FLOAT | NOT NULL |
| remediation_action | TEXT | NOT NULL |
| remediation_effort | VARCHAR(20) | NOT NULL |
| remediation_url | VARCHAR(500) | NULL |

**graph_nodes**

| Column | Type | Constraints |
|--------|------|------------|
| id | UUID | PK |
| scan_id | UUID | FK → scans(id), NOT NULL |
| platform | VARCHAR(100) | NOT NULL |
| identifier | VARCHAR(500) | NOT NULL |
| profile_url | VARCHAR(1000) | NOT NULL |
| confidence | FLOAT | NOT NULL |
| depth | INTEGER | NOT NULL |
| category | VARCHAR(50) | NOT NULL |
| raw_data | JSONB | default '{}' |

**graph_edges**

| Column | Type | Constraints |
|--------|------|------------|
| id | UUID | PK |
| scan_id | UUID | FK → scans(id), NOT NULL |
| source_node_id | UUID | FK → graph_nodes(id), NOT NULL |
| target_node_id | UUID | FK → graph_nodes(id), NOT NULL |
| evidence_type | VARCHAR(50) | NOT NULL |
| confidence | FLOAT | NOT NULL |

**audit_logs**

| Column | Type | Constraints |
|--------|------|------------|
| id | UUID | PK |
| scan_id | UUID | FK → scans(id), NOT NULL |
| event_type | VARCHAR(50) | NOT NULL |
| event_data | JSONB | NOT NULL |
| operator_ip | INET | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default now() |

---

## 7. Module interface specification

### 7.1 Base module interface

Every data source module shall implement the following abstract interface:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ModuleResult:
    module_name: str
    success: bool
    findings: list[Finding]
    graph_nodes: list[IdentityNode]
    graph_edges: list[IdentityEdge]
    errors: list[str]
    duration_seconds: float

class BaseModule(ABC):
    @abstractmethod
    async def execute(self, inputs: ScanInputs) -> ModuleResult:
        """Execute the module's data collection and analysis."""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Return the unique module identifier."""
        ...

    @abstractmethod
    def get_required_inputs(self) -> list[str]:
        """Return which input fields this module requires."""
        ...
```

### 7.2 Module registration

Modules shall be registered in the orchestrator via dependency injection, allowing new modules to be added without modifying orchestration logic:

```python
class ScanOrchestrator:
    def __init__(self, modules: list[BaseModule]):
        self._modules = modules

    async def execute_scan(self, inputs: ScanInputs) -> ScanResult:
        applicable = [m for m in self._modules 
                      if self._has_required_inputs(m, inputs)]
        results = await asyncio.gather(
            *[m.execute(inputs) for m in applicable],
            return_exceptions=True
        )
        # aggregate results...
```

---

## 8. Error handling specification

### 8.1 Error categories

| Category | HTTP status | Behavior |
|----------|------------|----------|
| Input validation failure | 422 | Return detailed validation errors, do not execute scan |
| API key missing or invalid | 500 (internal) | Log error, mark module as failed, continue scan with remaining modules |
| External API timeout | N/A (internal) | Retry up to 3 times with exponential backoff, then mark module as failed |
| External API rate limit (429) | N/A (internal) | Backoff per platform policy, retry, then mark as failed if still limited |
| External API server error (5xx) | N/A (internal) | Retry once, then mark module as failed |
| Graph crawler depth/node limit reached | N/A (internal) | Stop crawling, report partial graph with a note that limits were reached |
| Scan timeout reached | N/A (internal) | Cancel remaining tasks, report partial results |
| Database connection failure | 500 | Return service unavailable, trigger health check alert |
| Redis connection failure | 500 | Continue without cache (all requests go to source APIs), log degraded mode |

### 8.2 Partial results policy

When one or more modules fail, the system shall:

1. Mark those modules as failed in the scan status
2. Include a `modules_failed` array in the report metadata listing which modules failed and why
3. Compute the risk score based on available findings only
4. Add a note to the report: "The following data sources were unavailable during this scan: {list}. The risk score may be lower than the true exposure level."

---

## 9. Testing requirements

### 9.1 Test categories

| Category | Scope | Tools | Minimum coverage |
|----------|-------|-------|-----------------|
| Unit tests | Individual functions, classes, parsers | pytest, pytest-asyncio | 80% line coverage |
| Integration tests | Module → API interactions (with recorded responses) | pytest, respx (HTTP mocking) | All modules, happy + error paths |
| API tests | REST endpoint behavior | pytest, httpx.AsyncClient | All endpoints, all status codes |
| Scoring tests | Risk score determinism | pytest | 20+ known-outcome fixtures |
| Graph tests | Crawler cycle detection, depth limits, timeout | pytest | 10+ graph topology scenarios |
| Frontend tests | Component rendering, user interaction | Vitest, React Testing Library | All components |
| E2E tests | Full scan workflow | pytest (backend), Playwright (frontend) | 3 complete scan scenarios |

### 9.2 Test data

- All external API responses shall be recorded as JSON fixtures in `tests/fixtures/`
- Tests shall never make real network calls (all HTTP mocked via respx)
- Test fixtures shall include: normal response, empty response, rate limited response, server error response, and malformed response for each API
- Graph crawler tests shall use predefined graph topologies: linear chain, star pattern, diamond pattern, cycle, disconnected components

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| Attack surface | The sum of all points where an unauthorized user could attempt to access or extract data |
| Credential stuffing | Automated injection of breached username/password pairs to gain unauthorized access |
| Data broker | A company that collects and sells personal information |
| DMARC | Domain-based Message Authentication, Reporting and Conformance — email authentication protocol |
| Entity resolution | The process of determining that multiple data records refer to the same real-world entity |
| Force-directed layout | A graph drawing algorithm that simulates physical forces to position nodes |
| k-anonymity | A privacy technique where individual records are indistinguishable from at least k-1 others |
| OSINT | Open Source Intelligence — information collected from publicly available sources |
| SPF | Sender Policy Framework — email authentication method |
| Token bucket | A rate limiting algorithm that allows bursts up to a configured limit |
| UEBA | User and Entity Behavior Analytics |
| WHOIS | A protocol for querying databases that store registration information about domain names |

---

## Appendix A — Disclaimer text

The following disclaimer shall appear on every report:

> This report was generated by the Public Information Exposure Analyzer (PIEA). All information presented was collected exclusively from publicly available sources through official APIs and public records. No private data was accessed, no authentication was bypassed, and no platform terms of service were violated during this scan. This report is provided for informational and security awareness purposes only. It does not constitute legal advice. The risk score is an algorithmic estimate and may not reflect the complete exposure profile. The operator is responsible for ensuring proper authorization was obtained before conducting this scan.

---

## Appendix B — Supported platform categories

| Category | Description | Example platforms |
|----------|------------|-------------------|
| Development | Code hosting, package registries | GitHub, GitLab, Bitbucket, npm, PyPI, Docker Hub |
| Social | Social networking, microblogging | Twitter/X, Reddit, Mastodon, Hacker News |
| Professional | Career and business networking | LinkedIn (existence only), AngelList, Crunchbase |
| Creative | Portfolio and content creation | Medium, Dev.to, Behance, Dribbble, Flickr |
| Gaming | Game platforms and communities | Steam, Xbox Live, PSN, Twitch, Discord |
| Communication | Messaging and forums | Telegram, Keybase, Discourse instances |
| Media | Video and audio platforms | YouTube, Vimeo, SoundCloud, Spotify |
| E-commerce | Online marketplaces | eBay, Etsy, Amazon (wishlists) |
| Identity | Identity verification services | Gravatar, Keybase, about.me |
| Personal | Personal websites and blogs | Custom domains detected via DNS/WHOIS |
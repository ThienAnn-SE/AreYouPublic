# PIEA Coding Rules — Mandatory Development Skill

**Version:** 1.0  
**Applies to:** Every Python and TypeScript file in this project  
**Enforcement:** Claude Code must read this file before writing any code and follow every rule without exception

---

## Part 1 — Clean code principles

These principles apply to every function, class, and module in the project. They are not suggestions. They are constraints.

### 1.1 Naming

**Variables and functions use snake_case. Classes use PascalCase. Constants use UPPER_SNAKE_CASE. No exceptions.**

Names must reveal intent. A reader should understand what a variable holds or what a function does without reading its implementation.

```python
# WRONG — meaningless names
def proc(d, t):
    r = d.get(t)
    return r

# WRONG — abbreviated names
def get_usr_brch(eml):
    brch_lst = hibp.query(eml)
    return brch_lst

# CORRECT — intent-revealing names
def get_user_breaches(email_address: str) -> list[BreachRecord]:
    breach_records = hibp_client.query_breaches(email_address)
    return breach_records
```

**Naming conventions by context:**

| Context | Convention | Example |
|---------|-----------|---------|
| Function that returns bool | Prefix with `is_`, `has_`, `can_`, `should_` | `is_profile_public()` |
| Function that fetches data | Prefix with `get_`, `fetch_`, `query_`, `lookup_` | `fetch_github_profile()` |
| Function that transforms data | Prefix with `parse_`, `extract_`, `convert_`, `build_` | `parse_bio_links()` |
| Function that validates | Prefix with `validate_`, `check_`, `verify_` | `validate_email_format()` |
| Function that creates side effects | Prefix with `create_`, `save_`, `send_`, `delete_` | `save_scan_result()` |
| Async function | Same conventions — the `async` keyword is sufficient signal | `async def fetch_github_profile()` |
| Private method | Single underscore prefix | `_compute_weighted_score()` |
| Module-level constant | UPPER_SNAKE_CASE | `MAX_CRAWL_DEPTH = 3` |
| Type alias | PascalCase | `PlatformName = str` |
| Pydantic model | PascalCase with descriptive suffix | `ScanRequest`, `BreachFinding` |
| Enum | PascalCase class, UPPER_SNAKE_CASE members | `class RiskTier(Enum): LOW = "low"` |

**Forbidden naming patterns:**

- Single-letter variables except `i`, `j`, `k` in trivial loops and `e` in except clauses
- Hungarian notation (`str_name`, `lst_items`, `dict_config`)
- Generic names (`data`, `info`, `result`, `temp`, `obj`, `thing`, `item`) without a qualifying prefix
- Shadowing builtins (`id`, `type`, `list`, `dict`, `input`, `hash`, `format`)
- Names differing only by number (`result1`, `result2`) — use descriptive qualifiers instead

### 1.2 Functions

**Every function does exactly one thing. If you can describe what a function does using the word "and", it does too much — split it.**

```python
# WRONG — does two things: fetches AND scores
async def fetch_and_score_breaches(email: str) -> ScoredBreachResult:
    breaches = await hibp_client.query(email)
    score = sum(b.severity_weight for b in breaches)
    return ScoredBreachResult(breaches=breaches, score=score)

# CORRECT — two separate functions with single responsibilities
async def fetch_breaches(email: str) -> list[BreachRecord]:
    """Fetch all known breaches for the given email from HIBP."""
    return await hibp_client.query(email)

def compute_breach_score(breaches: list[BreachRecord]) -> float:
    """Compute the weighted risk score from a list of breach records."""
    return sum(breach.severity_weight for breach in breaches)
```

**Function rules:**

- Maximum 20 lines of logic (excluding docstring, type hints, and blank lines). If longer, extract helper functions.
- Maximum 4 parameters. If more are needed, group them into a dataclass or Pydantic model.
- No boolean flag parameters that change behavior. Write two separate functions instead.
- Early return pattern: handle error cases first, then the happy path. Do not nest the happy path inside conditionals.

```python
# WRONG — deeply nested
async def process_scan(scan_id: str) -> ScanResult:
    scan = await repo.get(scan_id)
    if scan is not None:
        if scan.status == "queued":
            if scan.consent_valid:
                # ... 4 levels deep
                return result
            else:
                raise ConsentError()
        else:
            raise InvalidStatusError()
    else:
        raise ScanNotFoundError()

# CORRECT — early returns, flat structure
async def process_scan(scan_id: str) -> ScanResult:
    scan = await repo.get(scan_id)
    if scan is None:
        raise ScanNotFoundError(scan_id)
    if scan.status != "queued":
        raise InvalidStatusError(scan.status)
    if not scan.consent_valid:
        raise ConsentError(scan_id)

    # Happy path at the lowest indentation level
    return await _execute_scan(scan)
```

### 1.3 Error handling

**Never use bare `except:`. Never catch `Exception` unless you re-raise it. Catch the specific exception you expect.**

```python
# WRONG
try:
    response = await client.get(url)
except:
    return None

# WRONG
try:
    response = await client.get(url)
except Exception:
    logger.error("Failed")
    return None

# CORRECT
try:
    response = await client.get(url)
except httpx.TimeoutException:
    logger.warning("Request to %s timed out after %ds", url, timeout)
    raise PlatformTimeoutError(platform=platform_name, url=url) from None
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 429:
        raise RateLimitExceededError(platform=platform_name) from exc
    raise PlatformAPIError(platform=platform_name, status=exc.response.status_code) from exc
```

**Error handling rules:**

- Every module defines its own exception hierarchy inheriting from a project-level base exception
- Exception classes live in the module that raises them (e.g., `modules/hibp.py` defines `HIBPError`)
- Error messages include context: what was being attempted, what went wrong, and what identifiers are relevant
- Never swallow exceptions silently (catch and do nothing)
- Use `from exc` or `from None` on every `raise` inside an except block to maintain or suppress the chain intentionally
- Log at the boundary where the error is handled, not where it is raised

### 1.4 Comments and documentation

**Code should be self-documenting through naming. Comments explain WHY, not WHAT.**

```python
# WRONG — comment says what the code obviously does
# Increment counter by one
counter += 1

# WRONG — comment restates the function name
# Get breaches for email
breaches = get_breaches(email)

# CORRECT — comment explains a non-obvious business reason
# HIBP rate limits to 1 request per 1500ms per API key.
# We add 100ms buffer to avoid edge-case 429 responses.
await asyncio.sleep(1.6)

# CORRECT — comment explains a workaround
# Mastodon API returns 410 Gone for suspended accounts,
# which httpx raises as HTTPStatusError. We treat this as "not found"
# rather than an error because the account effectively doesn't exist.
```

**Docstring rules (Google style):**

```python
async def fetch_github_profile(username: str, *, timeout: float = 10.0) -> GitHubProfile:
    """Fetch a public GitHub user profile via the REST API.

    Retrieves the full public profile for the given username including
    bio, linked accounts, and repository metadata. Uses authenticated
    requests when a GitHub token is configured.

    Args:
        username: The GitHub username to look up. Case-insensitive.
        timeout: HTTP request timeout in seconds.

    Returns:
        A GitHubProfile containing the parsed profile data.

    Raises:
        PlatformNotFoundError: If the username does not exist (HTTP 404).
        PlatformTimeoutError: If the request exceeds the timeout.
        RateLimitExceededError: If GitHub rate limit is exhausted.
    """
```

Every public function and class must have a docstring. Private functions (prefixed with `_`) should have a docstring if the logic is non-obvious. Docstrings on simple property methods and `__init__` that just assigns arguments are optional.

### 1.5 Don't Repeat Yourself (DRY)

**If the same logic appears in two or more places, extract it into a shared function or class.**

Common extraction targets in this project:

- HTTP request logic with retry and error handling → use a shared `resilient_request()` helper
- Platform URL formatting → use the platform registry, not hardcoded URLs
- Risk score computation for a finding type → use the taxonomy config, not inline weights
- Cache read/write patterns → use the shared cache layer, not direct Redis calls

**But do not over-abstract.** If two pieces of code look similar but serve different business purposes and are likely to diverge, keep them separate. Premature abstraction is worse than mild duplication.

### 1.6 SOLID principles applied to this project

**Single Responsibility:** Each module in `src/piea/modules/` does one thing — fetches data from one source and returns structured findings. The scoring logic lives in `src/piea/scoring/`, not inside the modules.

**Open/Closed:** New data source modules can be added by implementing `BaseModule` without modifying the orchestrator. New risk finding types can be added to `risk_taxonomy.json` without modifying the scorer.

**Liskov Substitution:** Every `BaseModule` subclass must honor the `ModuleResult` return contract. If a module cannot produce graph nodes (e.g., HIBP), it returns an empty list — never `None` or a different type.

**Interface Segregation:** Extractors (GitHub, Mastodon, etc.) implement only the methods they need. Do not add abstract methods to `BaseModule` that only some modules use.

**Dependency Inversion:** The orchestrator depends on the `BaseModule` abstract class, not on concrete modules. Modules depend on `httpx.AsyncClient` injected via constructor, not created internally.

---

## Part 2 — Python coding guidelines

### 2.1 Type annotations

**Every function parameter and return type must be annotated. No exceptions. Use Python 3.11+ syntax.**

```python
# Type annotation reference for this project

# Basic types
def process_name(name: str) -> str: ...
def count_findings(findings: list[Finding]) -> int: ...
def get_config(key: str) -> str | None: ...

# Collections
def get_platforms() -> list[PlatformConfig]: ...
def get_weights() -> dict[str, float]: ...
def get_unique_ids() -> set[str]: ...

# Union types (use | not Union)
def parse_input(value: str | int) -> str: ...
def get_result() -> BreachFinding | None: ...

# Callable
from collections.abc import Callable, Awaitable
def register_hook(callback: Callable[[str], Awaitable[None]]) -> None: ...

# Generics
from typing import TypeVar
T = TypeVar("T")
async def cached_fetch(key: str, factory: Callable[[], Awaitable[T]]) -> T: ...

# TypedDict for unstructured data from APIs
from typing import TypedDict
class GitHubAPIResponse(TypedDict):
    login: str
    name: str | None
    bio: str | None
    blog: str
    twitter_username: str | None

# Literal for constrained strings
from typing import Literal
RiskTierLabel = Literal["low", "moderate", "high", "critical"]
EvidenceType = Literal["api_field", "verified_link", "bio_mention", "same_username", "keybase_proof"]
```

**Type annotation rules:**

- Never use `Any` unless interfacing with a truly untyped external library (and add a `# type: ignore[...]` comment explaining why)
- Use `X | None` not `Optional[X]`
- Use `list[X]` not `List[X]` (lowercase generics, Python 3.11+)
- Use `dict[K, V]` not `Dict[K, V]`
- Use `tuple[X, Y]` not `Tuple[X, Y]`
- Use `collections.abc.Sequence` for read-only list parameters, `list` for mutable ones
- Return concrete types, accept abstract types (accept `Sequence`, return `list`)

### 2.2 Imports

**Import order (enforced by ruff):**

```python
# 1. Standard library
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

# 2. Third-party
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local
from piea.core.cache import CacheLayer
from piea.core.rate_limiter import RateLimiter
from piea.modules.base import BaseModule, ModuleResult
```

**Import rules:**

- Never use `from module import *`
- Never use relative imports (`from .base import ...`). Always use absolute imports from `piea.` root.
- Import specific names, not entire modules (unless the module name is short and used frequently like `asyncio`)
- Do not import inside functions unless there is a genuine circular import issue (document it with a comment if so)

### 2.3 Data models

**Use Pydantic models for API boundaries (request/response). Use dataclasses for internal data structures.**

```python
# API boundary — Pydantic model (validates input, serializes output)
from pydantic import BaseModel, Field, field_validator

class ScanRequest(BaseModel):
    """Input model for creating a new scan."""

    name: str | None = Field(None, min_length=1, max_length=255)
    email: str | None = Field(None, max_length=255)
    username: str | None = Field(None, min_length=1, max_length=39, pattern=r"^[a-zA-Z0-9_-]+$")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        if v is not None and "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower() if v else None

    model_config = {"str_strip_whitespace": True}


# Internal data structure — dataclass (no validation overhead)
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class IdentityNode:
    """A single platform presence in the identity graph."""

    platform: str
    identifier: str
    profile_url: str
    confidence: float
    discovered_at_depth: int
    raw_data: dict[str, object] = field(default_factory=dict)
```

**Data model rules:**

- Pydantic models: use `frozen=True` for response models (immutable after creation)
- Dataclasses: always use `frozen=True` and `slots=True` for internal data structures
- Never use raw dicts to pass structured data between functions. Define a model.
- All optional fields must have explicit defaults
- Enum values must be lowercase strings matching the API schema in SRS.md

### 2.4 Async patterns

**All I/O operations must be async. Never use synchronous I/O in async code.**

```python
# WRONG — synchronous I/O blocks the event loop
import requests
def fetch_profile(url: str) -> dict:
    response = requests.get(url)
    return response.json()

# WRONG — sync file I/O in async context
async def read_config() -> str:
    with open("config.json") as f:  # This blocks!
        return f.read()

# CORRECT — async HTTP
async def fetch_profile(url: str) -> dict[str, object]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

# CORRECT — async file I/O (use aiofiles or run in executor)
import aiofiles
async def read_config() -> str:
    async with aiofiles.open("config.json") as f:
        return await f.read()
```

**Async rules:**

- Use `httpx.AsyncClient` as a shared instance (injected via constructor), not created per-request
- Use `asyncio.gather()` for concurrent independent operations with `return_exceptions=True`
- Use `asyncio.Semaphore` to limit concurrency (e.g., max 50 concurrent platform checks)
- Use `asyncio.wait_for()` to enforce timeouts on any operation that could hang
- Never call `asyncio.run()` inside async code
- Never use `time.sleep()` in async code — use `await asyncio.sleep()`

```python
# Correct concurrency pattern for this project
async def check_all_platforms(
    username: str,
    platforms: list[PlatformConfig],
    max_concurrency: int = 50,
) -> list[PlatformCheckResult]:
    """Check username existence across all platforms with bounded concurrency."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _check_one(platform: PlatformConfig) -> PlatformCheckResult:
        async with semaphore:
            return await _check_platform(username, platform)

    results = await asyncio.gather(
        *[_check_one(p) for p in platforms],
        return_exceptions=True,
    )

    return [
        r if isinstance(r, PlatformCheckResult)
        else PlatformCheckResult(platform=p.name, status="error", error=str(r))
        for r, p in zip(results, platforms)
    ]
```

### 2.5 Logging

**Use the `logging` module. Never use `print()`. Never use f-strings in log calls (use % formatting for lazy evaluation).**

```python
import logging

logger = logging.getLogger(__name__)

# WRONG
print(f"Checking platform {platform_name}")
logger.info(f"Found {count} breaches for {email}")  # f-string evaluated even if INFO disabled

# CORRECT
logger.info("Checking platform %s", platform_name)
logger.info("Found %d breaches for %s", count, email)
logger.warning("Rate limited by %s, backing off %ds", platform_name, backoff_seconds)
logger.error("Failed to fetch profile from %s: %s", platform_name, error_message)
logger.debug("Raw API response from %s: %s", platform_name, response_body)
```

**Logging level guidelines:**

| Level | When to use | Example |
|-------|------------|---------|
| DEBUG | Detailed diagnostic info for developers | Raw API responses, cache hit/miss, exact URLs called |
| INFO | Normal operational events | Scan started, module completed, profile found |
| WARNING | Something unexpected but recoverable | Rate limited, API returned unexpected format, cache miss |
| ERROR | Something failed but the scan continues | Module failed, API unreachable after retries |
| CRITICAL | Something failed and the scan cannot continue | Database unreachable, configuration invalid |

**Sensitive data in logs:**

- Never log email addresses in full — mask as `j***@example.com`
- Never log passwords, API keys, or tokens
- Never log raw user input without sanitization
- Log scan IDs, platform names, and timestamps freely

### 2.6 Configuration

**All configuration comes from environment variables via pydantic-settings. Never hardcode configuration values.**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API keys
    hibp_api_key: str
    github_token: str = ""
    google_cse_api_key: str = ""
    google_cse_engine_id: str = ""
    hunter_api_key: str = ""

    # Infrastructure
    database_url: str = "postgresql+asyncpg://piea:password@localhost:5432/piea"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    # Scan limits
    scan_max_depth: int = 3
    scan_timeout_seconds: int = 120
    scan_max_nodes: int = 500
    scan_rate_limit_per_hour: int = 10

    # Cache
    cache_ttl_breach: int = 86400
    cache_ttl_profile: int = 3600

    # Application
    log_level: str = "INFO"
```

**Configuration rules:**

- Define one `Settings` class in `src/piea/config.py`
- Use FastAPI dependency injection to provide settings to endpoints and services
- Default values must be suitable for local development (localhost, default ports)
- Production values come exclusively from environment variables
- Never read `os.environ` directly — always go through the Settings class

---

## Part 3 — API documentation references

These are the authoritative references for every external library used in this project. When in doubt about a library's behavior, consult the official documentation — do not guess.

### 3.1 Core framework

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| FastAPI | https://fastapi.tiangolo.com | Dependency injection, async endpoints, exception handlers, middleware, background tasks |
| Pydantic v2 | https://docs.pydantic.dev/latest | Model validation, field validators, model_config, serialization, TypeAdapter |
| Uvicorn | https://www.uvicorn.org | Server configuration, logging, worker management |

### 3.2 Async HTTP

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| httpx | https://www.python-httpx.org | AsyncClient, timeouts, retry, transport, event hooks, status code handling |
| respx (testing) | https://lundberg.github.io/respx | Route patterns, mock responses, assertion helpers |

### 3.3 Database

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| SQLAlchemy 2.0 | https://docs.sqlalchemy.org/en/20 | Async session, declarative models, relationship, query API, connection pooling |
| asyncpg | https://magicstack.github.io/asyncpg | Connection parameters, prepared statements, type codecs |
| Alembic | https://alembic.sqlalchemy.org | Migration generation, async engine, revision management, autogenerate |

### 3.4 Task queue

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| Celery | https://docs.celeryq.dev/en/stable | Task definition, result backends, retry, rate limiting, signals, best practices |
| Redis (Python) | https://redis-py.readthedocs.io | Async client, connection pooling, pipelines, pub/sub |

### 3.5 DNS and domain

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| dnspython | https://dnspython.readthedocs.io | Resolver, query types (MX, TXT, CNAME), async resolver, exception handling |
| python-whois | https://pypi.org/project/python-whois | Query interface, parsing, exception handling |

### 3.6 Testing

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| pytest | https://docs.pytest.org/en/stable | Fixtures, parametrize, markers, conftest, assertion introspection |
| pytest-asyncio | https://pytest-asyncio.readthedocs.io | Async fixtures, event loop scope, auto mode |
| pytest-cov | https://pytest-cov.readthedocs.io | Coverage configuration, branch coverage, minimum threshold |

### 3.7 Dev tools

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| ruff | https://docs.astral.sh/ruff | Rule selection, per-file ignores, pyproject.toml configuration |
| mypy | https://mypy.readthedocs.io | Strict mode, plugin system, type stubs, error codes |

### 3.8 Frontend

| Library | Docs URL | Key pages to reference |
|---------|---------|----------------------|
| React 18 | https://react.dev | Hooks, state management, effects, concurrent features |
| React Router v6 | https://reactrouter.com | Route definitions, loaders, URL parameters |
| Recharts | https://recharts.org | RadialBarChart (for gauge), BarChart, responsive container |
| D3.js v7 | https://d3js.org | Force simulation, drag, zoom, selections |
| Axios | https://axios-http.com | Interceptors, error handling, typed responses |
| TailwindCSS | https://tailwindcss.com | Utility classes, responsive design, dark mode |

---

## Part 4 — Framework coding standards and best practices

### 4.1 FastAPI patterns

**Router organization:**

```python
# Each router in its own file under api/routes/
# src/piea/api/routes/scans.py

from fastapi import APIRouter, Depends, HTTPException, status
from piea.api.dependencies import get_scan_service, get_settings
from piea.api.schemas.scan_request import ScanRequest
from piea.api.schemas.scan_response import ScanResponse

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])

@router.post(
    "",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new exposure scan",
    description="Submits a new scan request. Requires valid consent attestation.",
)
async def create_scan(
    request: ScanRequest,
    scan_service: ScanService = Depends(get_scan_service),
) -> ScanResponse:
    """Create and queue a new exposure scan."""
    scan = await scan_service.create(request)
    return ScanResponse.from_domain(scan)
```

**Dependency injection:**

```python
# src/piea/api/dependencies.py

from functools import lru_cache
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from piea.config import Settings
from piea.db.session import get_async_session

@lru_cache
def get_settings() -> Settings:
    return Settings()

async def get_db(settings: Settings = Depends(get_settings)) -> AsyncSession:
    async with get_async_session(settings.database_url) as session:
        yield session

def get_scan_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ScanService:
    return ScanService(db=db, settings=settings)
```

**Exception handling:**

```python
# Define structured error responses, do not raise raw HTTPException with string details

from fastapi import Request
from fastapi.responses import JSONResponse

class APIError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message

class ScanNotFoundError(APIError):
    def __init__(self, scan_id: str) -> None:
        super().__init__(404, "SCAN_NOT_FOUND", f"Scan {scan_id} does not exist")

class ConsentRequiredError(APIError):
    def __init__(self) -> None:
        super().__init__(422, "CONSENT_REQUIRED", "Valid consent attestation is required")

# Register in main.py
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.message},
    )
```

**FastAPI rules:**

- Every endpoint must have `response_model` defined
- Every endpoint must have `status_code` explicitly set
- Every endpoint must have `summary` and `description` for OpenAPI docs
- Use `Depends()` for all service and configuration injection — never instantiate services inside endpoint functions
- Use `status.HTTP_*` constants, not magic numbers
- Return Pydantic models from endpoints, never raw dicts
- Use `BackgroundTasks` for fire-and-forget operations, Celery for long-running scans

### 4.2 SQLAlchemy 2.0 patterns

**Model definition:**

```python
# src/piea/db/models.py

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import String, Text, Float, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, INET, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    consent_record_id: Mapped[UUID] = mapped_column(ForeignKey("consent_records.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    consent_record: Mapped["ConsentRecord"] = relationship(back_populates="scans")
    findings: Mapped[list["Finding"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
```

**Session management:**

```python
# src/piea/db/session.py

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

def create_engine(database_url: str):
    return create_async_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )

@asynccontextmanager
async def get_async_session(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**SQLAlchemy rules:**

- Use the 2.0 style exclusively (`Mapped`, `mapped_column`, `select()` — never the legacy 1.x `Column` or `session.query()`)
- Always use `expire_on_commit=False` for async sessions
- Always use `pool_pre_ping=True` to handle stale connections
- Use `server_default=func.now()` for timestamps, not Python-side defaults
- Define all relationships explicitly with `back_populates`
- Use cascade `"all, delete-orphan"` on parent-side relationships where child records should not outlive the parent

### 4.3 Pydantic v2 patterns

```python
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

class ScanRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        frozen=False,  # Mutable for request models
    )

    name: str | None = Field(None, min_length=1, max_length=255, examples=["Jane Doe"])
    email: str | None = Field(None, max_length=255, examples=["jane@example.com"])
    username: str | None = Field(None, min_length=1, max_length=39, examples=["janedoe"])

    @model_validator(mode="after")
    def at_least_one_input(self) -> "ScanRequest":
        if not any([self.name, self.email, self.username]):
            raise ValueError("At least one input field must be provided")
        return self

class ScanResponse(BaseModel):
    model_config = ConfigDict(frozen=True)  # Immutable for response models

    scan_id: UUID
    status: str
    created_at: datetime

    @classmethod
    def from_domain(cls, scan: Scan) -> "ScanResponse":
        return cls(scan_id=scan.id, status=scan.status, created_at=scan.created_at)
```

**Pydantic rules:**

- Request models: mutable (`frozen=False`), with validation
- Response models: immutable (`frozen=True`), with `from_domain()` class method
- Always provide `examples` in Field definitions for OpenAPI documentation
- Use `model_validator(mode="after")` for cross-field validation
- Use `field_validator` for single-field validation
- Never expose ORM models directly in API responses — always map through a Pydantic response model

### 4.4 httpx client patterns

```python
# Shared client with connection pooling — create once, inject everywhere

from httpx import AsyncClient, Timeout, Limits

def create_http_client(
    timeout: float = 10.0,
    max_connections: int = 100,
    max_keepalive: int = 20,
) -> AsyncClient:
    """Create a configured httpx async client for external API calls."""
    return AsyncClient(
        timeout=Timeout(timeout, connect=5.0),
        limits=Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive,
        ),
        follow_redirects=True,
        headers={"User-Agent": "PIEA-Scanner/1.0 (security-assessment-tool)"},
    )
```

**httpx rules:**

- Create one `AsyncClient` per service scope (application lifetime), not per request
- Always set explicit timeouts — never rely on defaults
- Always set a descriptive `User-Agent` header
- Use `response.raise_for_status()` to convert HTTP errors to exceptions
- For APIs requiring auth, use `headers` parameter, not URL query strings for keys
- Close the client properly in application shutdown hooks

### 4.5 Celery task patterns

```python
from celery import Celery, Task
from piea.config import Settings

settings = Settings()
celery_app = Celery("piea", broker=settings.celery_broker_url)

class ScanTask(Task):
    """Base task class with error handling and retry logic."""
    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 60
    max_retries = 3
    acks_late = True
    reject_on_worker_lost = True

@celery_app.task(base=ScanTask, bind=True)
def execute_scan(self: ScanTask, scan_id: str) -> dict:
    """Execute a full exposure scan as a background task."""
    # Celery tasks run synchronously — use asyncio.run() at the boundary
    import asyncio
    return asyncio.run(_async_execute_scan(scan_id))
```

**Celery rules:**

- Use `acks_late=True` so tasks survive worker crashes
- Use `reject_on_worker_lost=True` for the same reason
- Use `bind=True` to access task instance for retry control
- Celery tasks are the sync/async boundary — use `asyncio.run()` inside the task
- Never pass large data as task arguments — pass the scan ID and load from database
- Set `task_serializer="json"` and `result_serializer="json"` in Celery config

### 4.6 Testing patterns

```python
# conftest.py — shared fixtures

import pytest
import respx
from httpx import AsyncClient
from piea.main import app
from piea.config import Settings

@pytest.fixture
def settings() -> Settings:
    return Settings(
        hibp_api_key="test-key",
        database_url="sqlite+aiosqlite:///test.db",
        redis_url="redis://localhost:6379/15",
    )

@pytest.fixture
async def api_client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def mock_github_api():
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("https://api.github.com/users/testuser").respond(
            200,
            json={"login": "testuser", "bio": "Security researcher", "blog": "https://test.dev"},
        )
        yield respx_mock
```

```python
# test_hibp.py — example unit test structure

import pytest
from piea.modules.hibp import HIBPModule

class TestHIBPModule:
    """Tests for the Have I Been Pwned module."""

    async def test_returns_breaches_for_known_email(
        self, hibp_module: HIBPModule, mock_hibp_api
    ) -> None:
        result = await hibp_module.execute(ScanInputs(email="test@example.com"))

        assert result.success is True
        assert len(result.findings) == 3
        assert result.findings[0].severity == "critical"

    async def test_returns_empty_for_clean_email(
        self, hibp_module: HIBPModule, mock_hibp_api_clean
    ) -> None:
        result = await hibp_module.execute(ScanInputs(email="clean@example.com"))

        assert result.success is True
        assert len(result.findings) == 0

    async def test_handles_rate_limit_gracefully(
        self, hibp_module: HIBPModule, mock_hibp_api_rate_limited
    ) -> None:
        result = await hibp_module.execute(ScanInputs(email="test@example.com"))

        assert result.success is False
        assert "rate limit" in result.errors[0].lower()

    async def test_requires_email_input(self, hibp_module: HIBPModule) -> None:
        with pytest.raises(ValueError, match="email is required"):
            await hibp_module.execute(ScanInputs(username="testuser"))
```

**Testing rules:**

- Test file mirrors source file: `src/piea/modules/hibp.py` → `tests/unit/test_hibp.py`
- Test class name: `Test` + class under test (e.g., `TestHIBPModule`)
- Test method name: `test_` + behavior being tested in plain English
- Every test has exactly one assertion concept (multiple `assert` calls are fine if they verify one behavior)
- Use `respx` to mock all HTTP calls — never make real network requests in tests
- Use fixtures for setup, not `setUp()` methods
- Use `pytest.raises` for expected exceptions, not try/except in tests
- Use `pytest.mark.parametrize` for testing multiple inputs against the same logic
- Use `pytest.mark.asyncio` for async tests (or set `asyncio_mode = "auto"` in pyproject.toml)

---

## Part 5 — File-level template

Every new Python file must follow this structure:

```python
"""Module description — one line explaining what this module does.

Extended description if needed. Explain the module's role in the system
and its primary responsibilities. Keep to 2-3 sentences maximum.
"""

# Standard library imports
import asyncio
import logging
from dataclasses import dataclass

# Third-party imports
import httpx
from pydantic import BaseModel

# Local imports
from piea.core.cache import CacheLayer
from piea.modules.base import BaseModule, ModuleResult

logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 10.0

# Type aliases (if needed)
PlatformName = str


# Exceptions specific to this module
class HIBPError(Exception):
    """Base exception for HIBP module failures."""


class HIBPRateLimitError(HIBPError):
    """Raised when HIBP API rate limit is exceeded."""


# Data models specific to this module
@dataclass(frozen=True, slots=True)
class BreachRecord:
    """A single breach record from HIBP."""
    name: str
    domain: str
    breach_date: str
    data_classes: tuple[str, ...]
    is_verified: bool


# Main class
class HIBPModule(BaseModule):
    """Queries Have I Been Pwned for email breach exposure."""

    def __init__(self, client: httpx.AsyncClient, api_key: str, cache: CacheLayer) -> None:
        self._client = client
        self._api_key = api_key
        self._cache = cache

    # ... implementation
```

---

## Part 6 — Forbidden patterns

The following patterns are explicitly banned in this project. If Claude Code writes any of these, it must be rewritten immediately.

| Forbidden pattern | Why | Do instead |
|------------------|-----|-----------|
| `from typing import Optional, List, Dict, Tuple` | Deprecated in Python 3.11+ | Use `X \| None`, `list[X]`, `dict[K,V]`, `tuple[X,Y]` |
| `except Exception: pass` | Silently swallows all errors | Catch specific exceptions and handle them |
| `print()` for any purpose | Not captured by logging infrastructure | Use `logger.info/warning/error()` |
| `os.environ["KEY"]` or `os.getenv("KEY")` | Bypasses centralized config | Use the `Settings` class |
| `import *` | Pollutes namespace, breaks static analysis | Import specific names |
| `time.sleep()` in async code | Blocks the event loop | Use `await asyncio.sleep()` |
| `requests.get()` | Synchronous, blocks event loop | Use `httpx.AsyncClient` |
| `json.loads(response.text)` | Redundant, httpx does this | Use `response.json()` |
| Raw SQL strings | SQL injection risk | Use SQLAlchemy ORM or parameterized queries |
| `datetime.now()` | Not timezone-aware | Use `datetime.now(timezone.utc)` |
| `== None` or `!= None` | Anti-pattern in Python | Use `is None` or `is not None` |
| `== True` or `== False` | Redundant comparison | Use `if value:` or `if not value:` |
| `dict()` constructor | Slower, less readable | Use `{}` literal |
| `list()` constructor with comprehension | Redundant | Use `[x for x in ...]` directly |
| Mutable default arguments | Shared state bug | Use `field(default_factory=list)` or `= None` with `or []` |
| Hardcoded URLs or API endpoints | Violates configuration principle | Use config or platform registry |
| `# TODO` or `# FIXME` without issue reference | Untracked technical debt | File as a Known Issue in PROGRESS.md |
| `typing.Any` without comment | Defeats type safety | Add `# type: ignore[...]` with explanation |
| Global mutable state | Thread/async unsafe | Use dependency injection |
| Nested functions deeper than 1 level | Hard to test, hard to read | Extract to module-level functions |

---

## Enforcement

Claude Code must run the following checks after every file is written or modified:

```bash
# Type checking — must pass with zero errors
mypy src/piea/ --strict

# Linting — must pass with zero warnings
ruff check src/piea/ tests/

# Formatting — must be applied
ruff format src/piea/ tests/

# Tests — must pass
pytest tests/ -v --tb=short
```

If any check fails, fix the issue before reporting the task as complete. Never skip these checks.
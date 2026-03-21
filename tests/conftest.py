"""Shared pytest fixtures for PIEA tests.

Fixture hierarchy:
  - db_session:  async SQLAlchemy session backed by an in-process SQLite
                 engine (overrides PostgreSQL-specific types for unit tests)
  - client:      httpx.AsyncClient wired to the FastAPI app via ASGITransport
  - consent_service: ConsentService bound to the test db_session

Integration tests that need real PostgreSQL should use a separate conftest
with a docker-based engine (added in later phases).
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from piea.db.models import Base

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine():
    """Create an async SQLite engine for unit tests.

    SQLite lacks INET and JSONB, so we register type adapters at the
    dialect level. For unit tests this is sufficient — integration tests
    use real PostgreSQL.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables from the ORM metadata.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session that rolls back after every test.

    Each test gets a clean database without re-creating tables.
    """
    session_factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def consent_service(db_session):
    """Provide a ConsentService bound to the test session."""
    from piea.core.consent import ConsentService

    return ConsentService(db_session)


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(db_session) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client that sends requests through the FastAPI app.

    Overrides the get_db dependency so routes use the test session
    (which rolls back after each test).
    """
    from piea.db.session import get_db
    from piea.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()

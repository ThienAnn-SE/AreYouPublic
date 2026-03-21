"""Shared pytest fixtures for PIEA tests.

Fixture hierarchy:
  - db_session:  async SQLAlchemy session backed by PostgreSQL (CI) or
                 in-process SQLite (local dev without DATABASE_URL set)
  - client:      httpx.AsyncClient wired to the FastAPI app via ASGITransport
  - consent_service: ConsentService bound to the test db_session

Integration tests that need real PostgreSQL should use a separate conftest
with a docker-based engine (added in later phases).
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from piea.db.models import Base


def _register_sqlite_type_overrides(engine):
    """Register type adapters so PostgreSQL-specific column types
    (INET, JSONB, PG_UUID) work with SQLite for unit tests."""
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    if not hasattr(SQLiteTypeCompiler, "visit_INET"):
        SQLiteTypeCompiler.visit_INET = lambda self, type_, **kw: "VARCHAR(45)"
    if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
        SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine():
    """Create an async database engine for tests.

    Uses DATABASE_URL environment variable if set (CI with PostgreSQL),
    otherwise falls back to SQLite in-memory for local development.
    """
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        engine = create_async_engine(database_url, echo=False)
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )
        _register_sqlite_type_overrides(engine)

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

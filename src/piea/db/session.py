"""Database session management for PIEA.

This module provides async database session management using SQLAlchemy 2.0.
The engine and session factory are module-level singletons — connection pools
are reused across requests rather than recreated per call.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from piea.config import settings

# Module-level engine — one pool shared for the lifetime of the process.
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.environment == "development",
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async DB session for the duration of a request.

    Commits on success, rolls back on exception, always closes the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

"""FastAPI dependency providers for PIEA.

Import these with Depends() in route handlers to get typed,
lifecycle-managed objects without any boilerplate in the routes.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from piea.core.consent import ConsentService
from piea.db.session import get_db


async def get_session(db: AsyncSession = Depends(get_db)) -> AsyncGenerator[AsyncSession, None]:
    """Re-export the DB session dependency under a shorter name."""
    yield db


async def get_consent_service(
    db: AsyncSession = Depends(get_db),
) -> ConsentService:
    """Provide a ConsentService bound to the current request's DB session."""
    return ConsentService(db)


def get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For from a proxy."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; the leftmost is the client.
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

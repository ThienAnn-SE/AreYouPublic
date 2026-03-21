"""FastAPI dependency providers for PIEA.

Import these with Depends() in route handlers to get typed,
lifecycle-managed objects without any boilerplate in the routes.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from piea.core.cache import CacheLayer
from piea.core.consent import ConsentService
from piea.db.session import get_db
from piea.modules.hibp import HIBPClient, HIBPModule


async def get_session(db: AsyncSession = Depends(get_db)) -> AsyncGenerator[AsyncSession, None]:
    """Re-export the DB session dependency under a shorter name."""
    yield db


async def get_consent_service(
    db: AsyncSession = Depends(get_db),
) -> ConsentService:
    """Provide a ConsentService bound to the current request's DB session."""
    return ConsentService(db)


def get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For from a proxy.

    WARNING: This trusts X-Forwarded-For, which is client-spoofable.
    Only accurate when deployed behind a trusted reverse proxy (e.g. nginx,
    ALB) that overwrites or appends to this header. Configure
    uvicorn --proxy-headers or FastAPI TrustedHostMiddleware in production.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_candidate = forwarded_for.split(",")[0].strip()
        # Basic validation: reject obviously malformed values
        if ip_candidate and len(ip_candidate) <= 45 and " " not in ip_candidate:
            return ip_candidate
    return request.client.host if request.client else "unknown"


async def get_cache_layer() -> AsyncGenerator[CacheLayer, None]:
    """Provide a CacheLayer instance with proper cleanup."""
    cache = CacheLayer()
    try:
        yield cache
    finally:
        await cache.close()


async def get_hibp_client() -> AsyncGenerator[HIBPClient, None]:
    """Provide an HIBPClient with proper cleanup."""
    client = HIBPClient()
    try:
        yield client
    finally:
        await client.close()


async def get_hibp_module(
    client: HIBPClient = Depends(get_hibp_client),
    cache: CacheLayer = Depends(get_cache_layer),
) -> AsyncGenerator[HIBPModule, None]:
    """Provide a fully-wired HIBPModule with caching."""
    module = HIBPModule(client=client, cache=cache)
    yield module

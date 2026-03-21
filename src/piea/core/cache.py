"""Redis-based caching layer for PIEA.

Provides a thin async wrapper around Redis for caching API responses.
Cache keys are prefixed by namespace to avoid collisions between modules.
All values are stored as JSON strings.

The cache is optional — if Redis is unavailable, operations silently
return cache misses. This supports the graceful degradation requirement.
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from piea.config import settings

logger = logging.getLogger(__name__)


class CacheLayer:
    """Async Redis cache with namespace prefixing and JSON serialization.

    Args:
        redis_client: Optional pre-configured async Redis client. If not
            provided, one will be created from settings.redis_url.
        key_prefix: Prefix for all keys managed by this instance.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,  # type: ignore[type-arg]
        key_prefix: str = "piea",
    ) -> None:
        self._owns_client = redis_client is None
        self._redis = redis_client or aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._prefix = key_prefix

    async def get(self, namespace: str, key: str) -> object | None:
        """Retrieve a cached value.

        Args:
            namespace: Cache namespace (e.g. "breach", "profile").
            key: The cache key within the namespace.

        Returns:
            The deserialized value, or None on cache miss or error.
        """
        full_key = f"{self._prefix}:{namespace}:{key}"
        try:
            raw = await self._redis.get(full_key)
        except aioredis.RedisError:
            logger.warning("Redis GET failed for key %s, treating as miss", full_key)
            return None

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to deserialize cached value for key %s", full_key)
            return None

    async def set(
        self,
        namespace: str,
        key: str,
        value: object,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store a value in the cache.

        Args:
            namespace: Cache namespace (e.g. "breach", "profile").
            key: The cache key within the namespace.
            value: JSON-serializable value to cache.
            ttl_seconds: Time-to-live in seconds. If None, the key persists
                until explicitly deleted or Redis evicts it.

        Returns:
            True if the value was stored, False on error.
        """
        # TODO(security): Encrypt PII at rest per SECURITY_WORKFLOW.md §3.4 / threat T8.
        # Breach data cached here may contain sensitive details linked to users.
        full_key = f"{self._prefix}:{namespace}:{key}"
        try:
            serialized = json.dumps(value)
            if ttl_seconds is not None:
                await self._redis.setex(full_key, ttl_seconds, serialized)
            else:
                await self._redis.set(full_key, serialized)
            return True
        except (aioredis.RedisError, TypeError, ValueError):
            logger.warning("Redis SET failed for key %s", full_key)
            return False

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a cached value.

        Args:
            namespace: Cache namespace.
            key: The cache key.

        Returns:
            True if the key was deleted, False on error.
        """
        full_key = f"{self._prefix}:{namespace}:{key}"
        try:
            await self._redis.delete(full_key)
            return True
        except aioredis.RedisError:
            logger.warning("Redis DELETE failed for key %s", full_key)
            return False

    async def close(self) -> None:
        """Close the Redis connection if we own it."""
        if self._owns_client:
            await self._redis.aclose()

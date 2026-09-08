"""
Redis Cache Service
Provides asynchronous caching for inference results with configurable TTL.
Uses SHA-256 hashed input text as cache keys to avoid storing sensitive data.
"""

import logging

import redis.asyncio as redis
from redis.asyncio import Redis

from backend.app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Async Redis cache wrapper for inference results.

    Features:
    - Connection pooling for efficient resource usage
    - Automatic serialization/deserialization of Pydantic models
    - Configurable TTL with default of 24 hours
    - Graceful degradation when Redis is unavailable
    """

    def __init__(self):
        self._redis: Redis | None = None
        self._connected: bool = False
        self._reconnect_timer: int = 30
        logger.info("CacheService created (Redis not yet connected).")

    async def _try_reconnect(self) -> None:
        """Periodic Redis reconnection attempt."""
        try:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await self._redis.ping()
            self._connected = True
            logger.info("CacheService: Redis reconnected.")
        except Exception:
            self._redis = None
            self._connected = False

    async def connect(self) -> None:
        """
        Establish connection to Redis with retry logic.
        Gracefully degrades if Redis is unavailable.
        """
        try:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            await self._redis.ping()
            self._connected = True
            logger.info(f"Redis connected: {settings.REDIS_URL}")

        except Exception as e:
            self._connected = False
            logger.warning(
                f"Redis connection failed: {e}. Caching will be disabled. Inference results will not be cached."
            )

    async def disconnect(self) -> None:
        """Gracefully close Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
                logger.info("Redis connection closed.")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
        self._connected = False

    async def get(self, key: str) -> str | None:
        """
        Retrieve a cached inference result by key.

        Args:
            key: SHA-256 hash of the input text

        Returns:
            JSON string of the cached result, or None if not found/unavailable
        """
        if not self._connected or not self._redis:
            return None

        try:
            value = await self._redis.get(key)
            if value:
                logger.debug(f"Cache HIT for key: {key[:16]}...")
            else:
                logger.debug(f"Cache MISS for key: {key[:16]}...")
            return value
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self._connected = False
            await self._try_reconnect()
            return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> bool:
        """
        Store an inference result in cache with TTL.

        Args:
            key: SHA-256 hash of the input text
            value: JSON-serialized InferenceResult
            ttl_seconds: Time-to-live in seconds (default: 24 hours)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self._connected or not self._redis:
            return False

        ttl = ttl_seconds or settings.REDIS_CACHE_TTL_SECONDS

        try:
            await self._redis.setex(key, ttl, value)
            logger.debug(f"Cached result for key: {key[:16]}... (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Remove a cached entry.

        Args:
            key: SHA-256 hash to remove

        Returns:
            True if deleted, False otherwise
        """
        if not self._connected or not self._redis:
            return False

        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def flush(self) -> bool:
        """
        Clear all cached entries. Use with caution.

        Returns:
            True if flushed successfully
        """
        if not self._connected or not self._redis:
            return False

        try:
            await self._redis.flushdb()
            logger.warning("Cache flushed completely.")
            return True
        except Exception as e:
            logger.error(f"Cache flush error: {e}")
            return False

    @property
    def is_available(self) -> bool:
        """Check if Redis cache is connected and available."""
        return self._connected and self._redis is not None

    async def health_check(self) -> dict:
        """Return cache health status for monitoring."""
        status: dict[str, bool | str | int] = {
            "connected": self._connected,
            "available": self.is_available,
        }

        if self._connected and self._redis:
            try:
                pong = await self._redis.ping()
                status["ping"] = pong
                # Get approximate key count
                dbsize = await self._redis.dbsize()
                status["cached_entries"] = dbsize
            except Exception as e:
                status["error"] = str(e)

        return status


# Global singleton
cache_service = CacheService()

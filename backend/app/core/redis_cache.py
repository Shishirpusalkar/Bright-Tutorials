"""
Redis caching service for PDF extraction results.

Implements the caching strategy described in docs/pdf_extraction_enhancement.md:
- Store extracted text and metadata in Redis for fast retrieval.
- TTL (time-to-live) policy for cache invalidation.
- Graceful fallback when Redis is unavailable.
"""

import json
import logging
from typing import Any

import redis as redis_lib

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis | None:
    """Return a Redis client, or None if Redis is unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis_lib.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        logger.info("Redis connection established: %s", settings.REDIS_URL)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable (%s). Caching disabled.", exc)
        return None


def _cache_key(pdf_hash: str) -> str:
    return f"pdf_extraction:{pdf_hash}"


def get_cached_extraction(pdf_hash: str) -> dict[str, Any] | None:
    """
    Retrieve previously cached extraction data for a PDF hash.

    Returns the cached dict, or None on cache miss / Redis unavailability.
    """
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(_cache_key(pdf_hash))
        if raw:
            logger.debug("Redis cache HIT for pdf_hash=%s", pdf_hash)
            return json.loads(raw)
        logger.debug("Redis cache MISS for pdf_hash=%s", pdf_hash)
        return None
    except Exception as exc:
        logger.warning("Redis get failed: %s", exc)
        return None


def set_cached_extraction(
    pdf_hash: str,
    data: dict[str, Any],
    ttl: int | None = None,
) -> bool:
    """
    Store extraction data in Redis with a TTL.

    Args:
        pdf_hash: SHA-256 hex digest of the PDF file content.
        data:     The extraction payload to cache.
        ttl:      Time-to-live in seconds. Defaults to settings.PDF_CACHE_TTL_SECONDS.

    Returns True on success, False otherwise.
    """
    client = get_redis()
    if client is None:
        return False
    ttl = ttl if ttl is not None else settings.PDF_CACHE_TTL_SECONDS
    try:
        client.set(_cache_key(pdf_hash), json.dumps(data), ex=ttl)
        logger.debug("Cached pdf_hash=%s in Redis (TTL=%ss)", pdf_hash, ttl)
        return True
    except Exception as exc:
        logger.warning("Redis set failed: %s", exc)
        return False


def invalidate_extraction(pdf_hash: str) -> bool:
    """
    Remove a cached entry for the given PDF hash.

    Returns True if the key existed and was deleted, False otherwise.
    """
    client = get_redis()
    if client is None:
        return False
    try:
        deleted = client.delete(_cache_key(pdf_hash))
        logger.debug("Invalidated pdf_hash=%s (deleted=%s)", pdf_hash, deleted)
        return bool(deleted)
    except Exception as exc:
        logger.warning("Redis delete failed: %s", exc)
        return False

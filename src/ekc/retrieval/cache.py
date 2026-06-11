"""
Redis query cache.
Caches (query_embedding_hex -> retrieved_chunk_ids + scores).
TTL: 24 hours. Top-500 queries covered by Zipfian distribution.
"""
import json
import hashlib
import logging
import numpy as np
import redis
from typing import Optional
from src.ekc.core.config import settings

logger = logging.getLogger(__name__)

CACHE_TTL = 86400      # 24 hours
CACHE_PREFIX = "ekc:query:"


class QueryCache:

    def __init__(self):
        self._client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
        )

    def _key(self, query: str, role: str = "default") -> str:
        h = hashlib.sha256(f"{role}:{query.lower().strip()}".encode()).hexdigest()[:16]
        return f"{CACHE_PREFIX}{h}"

    def get(self, query: str, role: str = "default") -> Optional[list[tuple[str, float]]]:
        try:
            val = self._client.get(self._key(query, role))
            if val:
                logger.debug(f"Cache HIT: '{query[:50]}'")
                return json.loads(val)
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
        return None

    def set(self, query: str, results: list[tuple[str, float]], role: str = "default"):
        try:
            self._client.setex(
                self._key(query, role),
                CACHE_TTL,
                json.dumps(results),
            )
            logger.debug(f"Cache SET: '{query[:50]}'")
        except Exception as e:
            logger.debug(f"Cache set error: {e}")

    def invalidate(self, query: str, role: str = "default"):
        try:
            self._client.delete(self._key(query, role))
        except Exception:
            pass
        
    def get_response(self, query: str, role: str = "default") -> dict | None:
        """Cache full LLM response including answer, sources, confidence."""
        try:
            val = self._client.get(f"resp:{self._key(query, role)}")
            if val:
                logger.debug(f"Response cache HIT: '{query[:50]}'")
                return json.loads(val)
        except Exception as e:
            logger.debug(f"Response cache get error: {e}")
        return None

    def set_response(self, query: str, response: dict, role: str = "default"):
        """Cache full LLM response for 24 hours."""
        try:
            self._client.setex(
                f"resp:{self._key(query, role)}",
                CACHE_TTL,
                json.dumps(response),
            )
            logger.debug(f"Response cache SET: '{query[:50]}'")
        except Exception as e:
            logger.debug(f"Response cache set error: {e}")


# ── Module-level singleton ────────────────────────────────────────────────────

_cache: Optional[QueryCache] = None


def get_cache() -> QueryCache:
    global _cache
    if _cache is None:
        _cache = QueryCache()
    return _cache
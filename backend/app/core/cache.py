"""
Redis cache wrapper with TTL support and permission-aware key generation.
"""

import hashlib
import json
from typing import Any, Generic, TypeVar

import redis.asyncio as redis

from app.config import settings

T = TypeVar("T")


class CacheService:
    """Async Redis cache service."""

    def __init__(self):
        self._client: redis.Redis | None = None

    async def get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(settings.redis.url, decode_responses=True)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, key: str) -> str | None:
        client = await self.get_client()
        return await client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> bool:
        client = await self.get_client()
        return await client.setex(key, ttl_seconds, value)

    async def get_json(self, key: str) -> Any | None:
        data = await self.get(key)
        return json.loads(data) if data else None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        return await self.set(key, json.dumps(value, ensure_ascii=False), ttl_seconds)

    async def delete(self, key: str) -> int:
        client = await self.get_client()
        return await client.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        client = await self.get_client()
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
        return 0

    def make_qa_cache_key(
        self,
        question: str,
        kb_id: str | None = None,
        datasource_id: str | None = None,
        permission_fingerprint: str = "",
    ) -> str:
        """
        Generate a cache key that includes permission fingerprint.
        Users with different permissions MUST NOT share cached results.
        """
        q_hash = hashlib.sha256(question.encode()).hexdigest()[:16]
        p_hash = hashlib.sha256(permission_fingerprint.encode()).hexdigest()[:12] if permission_fingerprint else "public"
        scope = kb_id or datasource_id or "global"
        return f"qa:{scope}:{q_hash}:{p_hash}"

    async def increment_rate_limit(self, key: str, limit: int, window_seconds: int = 60) -> tuple[int, bool]:
        """
        Atomic rate limit check. Returns (current_count, allowed).
        Uses Redis INCR + EXPIRE pattern.
        """
        client = await self.get_client()
        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        count = results[0]
        return count, count <= limit


cache_service = CacheService()

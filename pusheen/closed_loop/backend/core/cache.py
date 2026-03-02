import time
import hashlib
import json
from typing import Any

from .config import settings


class InMemoryCache:
    """Simple in-memory cache with TTL support for fast news loading."""

    def __init__(self, default_ttl: int | None = None):
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl or settings.CACHE_TTL_SECONDS

    def _make_key(self, prefix: str, params: dict | None = None) -> str:
        raw = prefix
        if params:
            raw += json.dumps(params, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, prefix: str, params: dict | None = None) -> Any | None:
        key = self._make_key(prefix, params)
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, prefix: str, value: Any, params: dict | None = None, ttl: int | None = None):
        key = self._make_key(prefix, params)
        expires_at = time.time() + (ttl or self._default_ttl)
        self._store[key] = (value, expires_at)

    def invalidate(self, prefix: str, params: dict | None = None):
        key = self._make_key(prefix, params)
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def cleanup_expired(self):
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]


# Global cache instances
news_cache = InMemoryCache(default_ttl=settings.CACHE_TTL_SECONDS)
summary_cache = InMemoryCache(default_ttl=3600)  # summaries cached 1 hour

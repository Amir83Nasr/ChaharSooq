"""Login rate limit — in-memory by default, Redis when configured.

Single-process dev/small-deploy guard with an upgrade path: set REDIS_URL and
all replicas share one sliding window. Without it we keep the previous
in-memory buckets (documented limitation, same as before).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Protocol

log = logging.getLogger("charsooq.rate_limit")

_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 10
RATE_WINDOW_S = 60.0


class RateLimiter(Protocol):
    def is_limited(self, key: str) -> bool: ...


class MemoryRateLimiter:
    """Per-process sliding window — dev / single replica only."""

    def is_limited(self, key: str) -> bool:
        now = time.monotonic()
        bucket = [t for t in _rate_buckets[key] if now - t < RATE_WINDOW_S]
        _rate_buckets[key] = bucket
        if len(bucket) >= RATE_LIMIT:
            return True
        bucket.append(now)
        return False


class RedisRateLimiter:
    """Shared sliding window via INCR+EXPIRE (fixed window, Redis-backed)."""

    def __init__(self, url: str) -> None:
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("redis package is required for REDIS_URL") from exc
        self._client = redis.Redis.from_url(url, socket_timeout=2.0)

    def is_limited(self, key: str) -> bool:
        rkey = f"charsooq:ratelimit:{key}"
        try:
            count = self._client.incr(rkey)
            if count == 1:
                self._client.expire(rkey, int(RATE_WINDOW_S))
            return count > RATE_LIMIT
        except Exception:
            log.warning("redis rate-limit unavailable, failing open", exc_info=True)
            return False


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Process-wide limiter — Redis when REDIS_URL is set, else memory."""
    global _limiter
    if _limiter is None:
        try:
            from app.core.config import get_settings

            url = get_settings().redis_url.strip()
        except Exception:
            url = ""
        if url:
            try:
                _limiter = RedisRateLimiter(url)
                log.info("rate limit: redis backend")
            except Exception:
                log.warning("rate limit: redis init failed, using memory", exc_info=True)
                _limiter = MemoryRateLimiter()
        else:
            _limiter = MemoryRateLimiter()
    return _limiter


def reset_rate_limits() -> None:
    """Test hook — clears in-memory login buckets between test clients."""
    global _limiter
    _rate_buckets.clear()
    _limiter = None


def rate_limited(key: str) -> bool:
    """Return True when `key` (IP or `ip:username`) exceeded the window."""
    return get_limiter().is_limited(key)


def login_rate_key(ip: str, username: str | None = None) -> str:
    """Combine IP with the attempted username so one user cannot lock all."""
    name = (username or "").strip().lower()
    return f"{ip}:{name}" if name else ip

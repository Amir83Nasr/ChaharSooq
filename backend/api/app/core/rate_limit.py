"""In-memory login rate limit — single-process dev/small-deploy guard.

# ponytail: multi-worker/Redis-backed limiter when login abuse or replicas arrive.
"""

import time
from collections import defaultdict

_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 10
RATE_WINDOW_S = 60.0


def reset_rate_limits() -> None:
    """Test hook — clears in-memory login buckets between test clients."""
    _rate_buckets.clear()


def _prune(now: float, key: str) -> list[float]:
    bucket = [t for t in _rate_buckets[key] if now - t < RATE_WINDOW_S]
    _rate_buckets[key] = bucket
    return bucket


def rate_limited(key: str) -> bool:
    """Return True when `key` (IP or `ip:username`) exceeded the window."""
    now = time.monotonic()
    bucket = _prune(now, key)
    if len(bucket) >= RATE_LIMIT:
        return True
    bucket.append(now)
    return False


def login_rate_key(ip: str, username: str | None = None) -> str:
    """Combine IP with the attempted username so one user cannot lock all."""
    name = (username or "").strip().lower()
    return f"{ip}:{name}" if name else ip

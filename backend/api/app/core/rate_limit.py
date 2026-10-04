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


def rate_limited(ip: str) -> bool:
    now = time.monotonic()
    bucket = [t for t in _rate_buckets[ip] if now - t < RATE_WINDOW_S]
    _rate_buckets[ip] = bucket
    if len(bucket) >= RATE_LIMIT:
        return True
    bucket.append(now)
    return False

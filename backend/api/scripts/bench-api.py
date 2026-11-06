"""API baseline benchmark — three representative reads, stdlib only.

Usage (API running locally, seeded dev DB):
    ADMIN_PASSWORD=secret123 python backend/api/scripts/bench-api.py

Measures wall time for:
  1. GET /api/v1/products (filtered + paginated)
  2. GET /api/v1/dashboard/overview
  3. GET /api/v1/dashboard/summary

Prints per-endpoint mean over N runs. Re-run after perf changes and record
the numbers in docs/perf-baseline.md. Not part of CI (needs a live server).
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = os.environ.get("BENCH_BASE_URL", "http://localhost:8000")
RUNS = int(os.environ.get("BENCH_RUNS", "5"))
USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SCENARIOS: list[tuple[str, str]] = [
    ("products-filtered", "/api/v1/products?q=CHE&sort=cheapest&page=1&page_size=20"),
    ("dashboard-overview", "/api/v1/dashboard/overview?threshold=5"),
    ("dashboard-summary", "/api/v1/dashboard/summary?threshold=5&gap_limit=8"),
]


def _opener() -> urllib.request.OpenerDirector:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return opener


def login(opener: urllib.request.OpenerDirector) -> None:
    payload = json.dumps({"username": USERNAME, "password": PASSWORD}).encode()
    req = urllib.request.Request(
        urllib.parse.urljoin(BASE, "/api/v1/auth/login"),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(req, timeout=10) as res:
            if res.status != 200:
                raise RuntimeError(f"login failed: HTTP {res.status}")
    except Exception as exc:
        raise RuntimeError(
            f"login failed — is the API running at {BASE}? "
            f"(set BENCH_BASE_URL / ADMIN_PASSWORD): {exc}"
        ) from exc


def bench(opener: urllib.request.OpenerDirector, path: str) -> float:
    url = urllib.parse.urljoin(BASE, path)
    best: list[float] = []
    for _ in range(RUNS):
        req = urllib.request.Request(url, method="GET")
        start = time.perf_counter()
        with opener.open(req, timeout=30) as res:
            res.read()
            assert res.status == 200, f"{path}: HTTP {res.status}"
        best.append((time.perf_counter() - start) * 1000)
    return statistics.mean(best)


def main() -> int:
    if not PASSWORD:
        print("ADMIN_PASSWORD is required", file=sys.stderr)
        return 2
    opener = _opener()
    login(opener)
    print(f"base={BASE} runs={RUNS}")
    for name, path in SCENARIOS:
        mean_ms = bench(opener, path)
        print(f"{name:20s} {mean_ms:8.1f} ms (mean of {RUNS})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

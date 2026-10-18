"""Tiny in-memory sliding-window limiter (single process). Behind several workers use a shared store (Redis) or a proxy."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_hits: dict[str, deque[float]] = defaultdict(deque)


def check(bucket: str, limit: int, window_s: float) -> bool:
    now = time.monotonic()
    q = _hits[bucket]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def enforce(bucket: str, limit: int, window_s: float) -> None:
    if not check(bucket, limit, window_s):
        raise HTTPException(429, "Too many requests. Please wait a moment and try again.")


def reset() -> None:
    _hits.clear()

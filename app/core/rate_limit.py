import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Простой in-memory rate limiter для dev-режима.

    На проде заменить на Redis-реализацию (INCR + EXPIRE).
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Slow down.",
                )
            bucket.append(now)


# Готовые лимитеры под типовые роуты
auth_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)
message_limiter = InMemoryRateLimiter(max_requests=30, window_seconds=10)
search_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=10)


def client_key(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


def rate_limit_auth(request: Request) -> None:
    auth_limiter.check(client_key(request))


def rate_limit_message(request: Request) -> None:
    message_limiter.check(client_key(request))


def rate_limit_search(request: Request) -> None:
    search_limiter.check(client_key(request))
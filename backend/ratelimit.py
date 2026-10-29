"""A per-IP, per-route request limit over a sliding minute, kept in memory."""

import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple

from fastapi.responses import JSONResponse

WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(self, limits: Dict[Tuple[str, str], int], clock=time.monotonic):
        self.limits = limits
        self.clock = clock
        self.hits: Dict[tuple, deque] = defaultdict(deque)

    def allow(self, client: str, method: str, path: str) -> bool:
        limit = self.limits.get((method, path))
        if limit is None:
            return True
        now = self.clock()
        hits = self.hits[(client, method, path)]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def rate_limit_middleware(limiter: RateLimiter):
    async def middleware(request, call_next):
        client: Optional[str] = request.client.host if request.client else "unknown"
        if not limiter.allow(client, request.method, request.url.path):
            return JSONResponse({"detail": "Too many requests, slow down a little."}, status_code=429)
        return await call_next(request)
    return middleware

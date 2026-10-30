"""A per-IP, per-route limit over a sliding minute, kept in memory.

A route ending in /* covers every path under it, in one shared count: limiting each room
code on its own would let someone guess as many codes as they like.
"""

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
        self.last_forget = clock()

    def route(self, method: str, path: str) -> Optional[str]:
        if (method, path) in self.limits:
            return path
        return next((route for m, route in self.limits
                     if m == method and route.endswith("/*") and path.startswith(route[:-1])), None)

    def allow(self, client: str, method: str, path: str) -> bool:
        route = self.route(method, path)
        if route is None:
            return True
        limit = self.limits[(method, route)]
        now = self.clock()
        self.forget_old(now)
        hits = self.hits[(client, method, route)]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    def forget_old(self, now: float) -> None:
        """Once a minute, drops the clients with no hit left in the window."""
        if now - self.last_forget <= WINDOW_SECONDS:
            return
        self.last_forget = now
        for key in [key for key, hits in self.hits.items() if not hits or now - hits[-1] > WINDOW_SECONDS]:
            del self.hits[key]


def rate_limit_middleware(limiter: RateLimiter):
    async def middleware(request, call_next):
        client: Optional[str] = request.client.host if request.client else "unknown"
        if not limiter.allow(client, request.method, request.url.path):
            return JSONResponse({"detail": "Too many requests, slow down a little."}, status_code=429)
        return await call_next(request)
    return middleware

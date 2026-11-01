"""A per-IP, per-route limit over a sliding minute, kept in memory.

A route ending in /* covers every path under it, in one shared count: limiting each room
code on its own would let someone guess as many codes as they like.
"""

import ipaddress
import time
from collections import Counter, defaultdict, deque
from typing import Dict, Optional, Tuple

from fastapi.responses import JSONResponse

WINDOW_SECONDS = 60.0


def client_key(host: Optional[str]) -> str:
    """Who a limit counts against. One IPv6 customer usually holds a whole /64, so a new
    address per request must not mean a new count."""
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return host or "unknown"
    return str(ipaddress.ip_network((address, 64), strict=False)) if address.version == 6 else str(address)


class RateLimiter:
    def __init__(self, limits: Dict[Tuple[str, str], int], clock=time.monotonic,
                 max_sockets: Optional[int] = None):
        self.limits = limits
        self.clock = clock
        self.max_sockets = max_sockets
        self.sockets: Counter = Counter()
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

    def open_socket(self, client: str) -> bool:
        """Counts a WebSocket against its client; False when they hold too many already."""
        if self.max_sockets is not None and self.sockets[client] >= self.max_sockets:
            return False
        self.sockets[client] += 1
        return True

    def close_socket(self, client: str) -> None:
        self.sockets[client] -= 1
        if self.sockets[client] <= 0:
            del self.sockets[client]

    def forget_old(self, now: float) -> None:
        """Once a minute, drops the clients with no hit left in the window."""
        if now - self.last_forget <= WINDOW_SECONDS:
            return
        self.last_forget = now
        for key in [key for key, hits in self.hits.items() if not hits or now - hits[-1] > WINDOW_SECONDS]:
            del self.hits[key]


def rate_limit_middleware(limiter: RateLimiter):
    async def middleware(request, call_next):
        client = client_key(request.client.host if request.client else None)
        if not limiter.allow(client, request.method, request.url.path):
            return JSONResponse({"detail": "Too many requests, slow down a little."}, status_code=429)
        return await call_next(request)
    return middleware

"""Settings read from the environment (see .env.example)."""

import os


def _list(name: str, default: str):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# Origins allowed to call the API from another site; the game itself is same-origin
ALLOWED_ORIGINS = _list("HOOPGRID_ALLOWED_ORIGINS", "*")

# Shared secret for /admin/reload; empty disables the endpoint
ADMIN_TOKEN = os.environ.get("HOOPGRID_ADMIN_TOKEN", "")

# Requests per client IP and minute; HOOPGRID_RATE_LIMIT=0 turns limiting off
RATE_LIMITS_ENABLED = os.environ.get("HOOPGRID_RATE_LIMIT", "1") != "0"
RATE_LIMITS = {
    ("POST", "/api/rooms"): 10,
    ("GET", "/api/rooms/*"): 30,  # every code counts together, so codes can't be guessed
    ("WS", "/ws/rooms/*"): 30,    # joins and reconnects
    ("WS", "message"): 240,       # sent on a room socket; a player sends a few each turn
    ("POST", "/api/new-game"): 60,  # every drawn grid is a new game
    ("GET", "/api/search-players"): 240,
    ("GET", "/api/players"): 30,  # the whole name list; a page loads it once per league
}

# Games older than this are dropped from memory
GAME_MAX_AGE_SECONDS = 6 * 60 * 60

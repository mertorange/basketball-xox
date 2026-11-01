"""FastAPI application: loads the player catalogs once and serves the API and the frontend."""

import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import build_router
from .catalog.criteria import build_index
from .catalog.players import load_catalogs
from .game.manager import GameManager
from .online.rooms import RoomManager
from .online.ws import build_online_router
from .ratelimit import RateLimiter, rate_limit_middleware

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def load_indexes():
    return {league: build_index(catalog) for league, catalog in load_catalogs().items()}


SECURITY_HEADERS = {
    "Content-Security-Policy": "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self' ws: wss:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}


def create_app(room_manager_options: dict = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cleanup = asyncio.create_task(app.state.room_manager.cleanup_loop())
        yield
        cleanup.cancel()

    # No /docs or /openapi.json: the API serves this game's own page and nobody else
    app = FastAPI(title="Hoop-Tac-Toe", description="2-Player Basketball Grid Tic-Tac-Toe", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["*"],
                       allow_headers=["*"])
    limiter = (RateLimiter(config.RATE_LIMITS, max_sockets=config.MAX_SOCKETS_PER_IP)
               if config.RATE_LIMITS_ENABLED else RateLimiter({}))
    app.middleware("http")(rate_limit_middleware(limiter))

    app.state.game_manager = GameManager(load_indexes(), max_same_device=config.MAX_SAME_DEVICE_GAMES)
    # Rooms live in this process's memory: run a single worker (see README)
    options = {"game_max_age": config.GAME_MAX_AGE_SECONDS, **(room_manager_options or {})}
    app.state.room_manager = RoomManager(app.state.game_manager, **options)
    app.include_router(build_router(app.state.game_manager))
    app.include_router(build_online_router(app.state.room_manager, limiter, config.ALLOWED_ORIGINS))

    @app.get("/health", include_in_schema=False)
    def health():
        games = app.state.game_manager
        return {
            "status": "ok",
            "players": {league: len(index.catalog.players) for league, index in games.indexes.items()},
            "rooms": len(app.state.room_manager.rooms),
            "games": len(games.active_games),
        }

    @app.post("/admin/reload", include_in_schema=False)
    def reload_data(x_admin_token: str = Header("")):
        """Loads the datasets again (after a data refresh) without dropping open rooms."""
        if not config.ADMIN_TOKEN or not secrets.compare_digest(x_admin_token.encode(), config.ADMIN_TOKEN.encode()):
            raise HTTPException(status_code=403, detail="Forbidden")
        indexes = load_indexes()
        app.state.game_manager.replace_indexes(indexes)
        return {"players": {league: len(index.catalog.players) for league, index in indexes.items()}}

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.middleware("http")
    async def limit_body_and_set_headers(request, call_next):
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > config.MAX_BODY_BYTES:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        # ES modules are imported without version strings; make browsers check for changes
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Hoop-Tac-Toe API is running."}

    return app


app = create_app()

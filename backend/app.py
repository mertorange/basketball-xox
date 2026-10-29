"""FastAPI application: loads the player catalogs once and serves the API and the frontend."""

import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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


def create_app(room_manager_options: dict = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cleanup = asyncio.create_task(app.state.room_manager.cleanup_loop())
        yield
        cleanup.cancel()

    app = FastAPI(title="Hoop Grid", description="2-Player Basketball Grid Tic-Tac-Toe", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["*"],
                       allow_headers=["*"])
    if config.RATE_LIMITS_ENABLED:
        app.middleware("http")(rate_limit_middleware(RateLimiter(config.RATE_LIMITS)))

    app.state.game_manager = GameManager(load_indexes())
    # Rooms live in this process's memory: run a single worker (see README)
    options = {"game_max_age": config.GAME_MAX_AGE_SECONDS, **(room_manager_options or {})}
    app.state.room_manager = RoomManager(app.state.game_manager, **options)
    app.include_router(build_router(app.state.game_manager))
    app.include_router(build_online_router(app.state.room_manager))

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
        if not config.ADMIN_TOKEN or not secrets.compare_digest(x_admin_token, config.ADMIN_TOKEN):
            raise HTTPException(status_code=403, detail="Forbidden")
        indexes = load_indexes()
        app.state.game_manager.replace_indexes(indexes)
        return {"players": {league: len(index.catalog.players) for league, index in indexes.items()}}

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.middleware("http")
    async def revalidate_static(request, call_next):
        # ES modules are imported without version strings; make browsers check for changes
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Hoop Grid API is running."}

    return app


app = create_app()

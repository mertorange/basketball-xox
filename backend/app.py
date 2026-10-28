"""FastAPI application: loads the player catalogs once and serves the API and the frontend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import build_router
from .catalog.criteria import build_index
from .catalog.players import load_catalogs
from .game.manager import GameManager

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(title="Hoop Grid", description="2-Player Basketball Grid Tic-Tac-Toe")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    indexes = {league: build_index(catalog) for league, catalog in load_catalogs().items()}
    app.state.game_manager = GameManager(indexes)
    app.include_router(build_router(app.state.game_manager))

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

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List

from .models import GameState, MoveRequest, MoveResult
from .game_engine import BasketballDataStore, GameManager

app = FastAPI(title="Basketball XOX", description="2-Player Basketball Tic-Tac-Toe Trivia")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_store = BasketballDataStore()
game_manager = GameManager(data_store)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

class NewGameRequest(BaseModel):
    league: str = "nba"
    player1_name: str = "Player 1"
    player2_name: str = "Player 2"

@app.post("/api/new-game", response_model=GameState)
def create_new_game(req: NewGameRequest):
    return game_manager.create_game(
        league=req.league,
        player1_name=req.player1_name,
        player2_name=req.player2_name
    )

@app.get("/api/game/{game_id}", response_model=GameState)
def get_game(game_id: str):
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

@app.post("/api/move", response_model=MoveResult)
def submit_move(req: MoveRequest):
    return game_manager.make_move(
        game_id=req.game_id,
        row=req.row,
        col=req.col,
        player_name=req.player_name
    )

@app.get("/api/search-players")
def search_players(
    q: str = Query(..., min_length=1),
    league: str = Query("nba")
):
    results = data_store.search_players(league=league, query=q, limit=8)
    return results

@app.get("/api/cell-info/{game_id}/{row}/{col}")
def get_cell_info(game_id: str, row: int, col: int):
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if not (0 <= row < 3 and 0 <= col < 3):
        raise HTTPException(status_code=400, detail="Invalid row/col")

    r_crit = game.row_criteria[row]
    c_crit = game.col_criteria[col]
    valid_players = data_store.get_valid_players_for_cell(game.league, r_crit, c_crit)

    return {
        "row_criteria": r_crit.display,
        "col_criteria": c_crit.display,
        "count_valid_players": len(valid_players),
        "claimed_by": game.grid[row][col].claimed_by,
        "player_name": game.grid[row][col].player_name
    }

# Mount frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Basketball XOX API is running. Frontend index not found."}

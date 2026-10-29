"""HTTP routes. Each one is a thin wrapper over the game manager or a player catalog."""

from fastapi import APIRouter, HTTPException, Query

from .models import GameState, MoveRequest, MoveResult, NewGameRequest, ShotClockViolationRequest


def build_router(game_manager) -> APIRouter:
    router = APIRouter(prefix="/api")

    def game_or_404(game_id: str) -> GameState:
        game = game_manager.get_game(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        return game

    @router.post("/new-game", response_model=GameState)
    def create_new_game(req: NewGameRequest):
        return game_manager.create_game(
            league=req.league,
            player1_name=req.player1_name,
            player2_name=req.player2_name,
            min_answers=req.min_answers,
            shot_clock=req.shot_clock,
            grid_style=req.grid_style,
            first_player=req.first_player,
        )

    @router.get("/game/{game_id}", response_model=GameState)
    def get_game(game_id: str):
        return game_or_404(game_id)

    @router.get("/game/{game_id}/answers")
    def get_answers(game_id: str):
        """Only for finished games: the answer key never leaves the server mid-game."""
        game_or_404(game_id)
        answers = game_manager.answers(game_id)
        if answers is None:
            raise HTTPException(status_code=409, detail="Answers are shown when the game is over")
        return {"game_id": game_id, "cells": answers}

    @router.post("/move", response_model=MoveResult)
    def submit_move(req: MoveRequest):
        return game_manager.make_move(game_id=req.game_id, row=req.row, col=req.col, player_name=req.player_name)

    @router.post("/shot-clock-violation")
    def handle_shot_clock_violation(req: ShotClockViolationRequest):
        game = game_manager.trigger_shot_clock_violation(req.game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found or finished")
        return {
            "success": True,
            "message": f"Shot clock expired! Turn forfeited to Player {game.current_player}.",
            "current_player": game.current_player,
        }

    @router.get("/search-players")
    def search_players(q: str = Query(..., min_length=1, max_length=80), league: str = Query("nba")):
        index = game_manager.indexes.get(league.lower())
        if not index:
            raise HTTPException(status_code=400, detail="Unknown league")
        # Names only: teams, country or awards in the response would hand out the answers
        return [{"name": p["name"]} for p in index.catalog.search(q, limit=8)]

    @router.get("/cell-info/{game_id}/{row}/{col}")
    def get_cell_info(game_id: str, row: int, col: int):
        game = game_or_404(game_id)
        if not (0 <= row < 3 and 0 <= col < 3):
            raise HTTPException(status_code=400, detail="Invalid coordinates")
        index = game_manager.index_for(game)
        r, c = game.row_criteria[row], game.col_criteria[col]
        valid = index.answers(index.get(r.type.value, r.value), index.get(c.type.value, c.value))
        return {
            "row_criteria": r.display,
            "col_criteria": c.display,
            "count_valid_players": len(valid),
            "claimed_by": game.grid[row][col].claimed_by,
            "player_name": game.grid[row][col].player_name,
        }

    return router

"""HTTP routes. Each one is a thin wrapper over the game manager or a player catalog."""

from fastapi import APIRouter, HTTPException, Query

from .models import GameRequest, GameState, MoveRequest, MoveResult, NewGameRequest


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

    def same_device_game(game_id: str) -> GameState:
        """Routes that change a game serve same-device games only: an online game's id reaches
        everyone in its room, spectators included, so its moves must go through the room."""
        game = game_or_404(game_id)
        if game_id in game_manager.online_games:
            raise HTTPException(status_code=409, detail="Online games are played through their room")
        return game

    def running_same_device_game(game_id: str) -> GameState:
        game = same_device_game(game_id)
        if game.status == "finished":
            raise HTTPException(status_code=409, detail="The game is over")
        return game

    @router.post("/move", response_model=MoveResult)
    def submit_move(req: MoveRequest):
        same_device_game(req.game_id)
        return game_manager.make_move(game_id=req.game_id, row=req.row, col=req.col, player_name=req.player_name)

    @router.post("/skip-turn")
    def skip_turn(req: GameRequest):
        running_same_device_game(req.game_id)
        game = game_manager.skip_turn(req.game_id)
        return {"success": True, "current_player": game.current_player}

    @router.post("/draw", response_model=GameState)
    def end_in_draw(req: GameRequest):
        """Same device: both players are at the screen, so the button press is the agreement."""
        running_same_device_game(req.game_id)
        return game_manager.end_in_draw(req.game_id)

    @router.post("/shot-clock-violation")
    def handle_shot_clock_violation(req: GameRequest):
        running_same_device_game(req.game_id)
        game = game_manager.trigger_shot_clock_violation(req.game_id)
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

    return router

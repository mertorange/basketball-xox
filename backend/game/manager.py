"""Running games: creation, moves, turnovers and results."""

import time
import uuid
from typing import Dict, List, Optional, Set

from ..catalog.criteria import CriteriaIndex, CriterionSpec
from ..catalog.players import notability
from ..models import Cell, Criterion, GameState, MoveResult
from .board import BoardGenerator
from .rules import is_full, other_player, winning_line

LEAGUE_LABELS = {"nba": "NBA", "euroleague": "EUROLEAGUE"}


def to_criterion(spec: CriterionSpec) -> Criterion:
    return Criterion(type=spec.kind, value=spec.value, display=spec.label)


class GameManager:
    def __init__(self, indexes: Dict[str, CriteriaIndex]):
        self.active_games: Dict[str, GameState] = {}
        # Each game keeps the criteria index it was created with, so a data reload
        # mid-game never changes the answers to a grid already on screen
        self.game_indexes: Dict[str, CriteriaIndex] = {}
        self.created_at: Dict[str, float] = {}
        # Games run by an online room; the same-device routes must not touch them
        self.online_games: Set[str] = set()
        self.replace_indexes(indexes)

    def replace_indexes(self, indexes: Dict[str, CriteriaIndex]) -> None:
        """New player data: new games use it, running games finish on their own."""
        self.indexes = indexes
        self.generators = {league: BoardGenerator(index) for league, index in indexes.items()}

    def create_game(self, league: str = "nba", player1_name: str = "Player 1", player2_name: str = "Player 2",
                    difficulty: str = "medium", shot_clock: Optional[int] = 60, grid_style: str = "mixed",
                    first_player: str = "X", online: bool = False,
                    categories: Optional[List[str]] = None) -> GameState:
        if grid_style != "custom":
            categories = None
        rows, cols = self.generators[league].generate(grid_style, difficulty, categories)
        game = GameState(
            game_id=uuid.uuid4().hex[:8],
            league=LEAGUE_LABELS[league],
            grid_style=grid_style,
            categories=categories,
            difficulty=difficulty,
            shot_clock=shot_clock,
            row_criteria=[to_criterion(s) for s in rows],
            col_criteria=[to_criterion(s) for s in cols],
            grid=[[Cell(row=r, col=c) for c in range(3)] for r in range(3)],
            current_player=first_player,
            player1_name=player1_name.strip() or "Player 1",
            player2_name=player2_name.strip() or "Player 2",
        )
        self.active_games[game.game_id] = game
        self.game_indexes[game.game_id] = self.indexes[league]
        self.created_at[game.game_id] = time.monotonic()
        if online:
            self.online_games.add(game.game_id)
        return game

    def get_game(self, game_id: str) -> Optional[GameState]:
        return self.active_games.get(game_id)

    def index_for(self, game: GameState) -> CriteriaIndex:
        return self.game_indexes.get(game.game_id) or self.indexes[game.league.lower()]

    def skip_turn(self, game_id: str) -> Optional[GameState]:
        """The player on the clock passes (or ran out of time); None if the game is not running."""
        game = self.active_games.get(game_id)
        if not game or game.status == "finished":
            return None
        game.current_player = other_player(game.current_player)
        return game

    trigger_shot_clock_violation = skip_turn

    def end_in_draw(self, game_id: str) -> Optional[GameState]:
        """Both players agreed to stop: the game ends as a draw."""
        game = self.active_games.get(game_id)
        if not game or game.status == "finished":
            return None
        game.status, game.winner = "finished", "DRAW"
        return game

    def make_move(self, game_id: str, row: int, col: int, player_name: str) -> MoveResult:
        game = self.active_games.get(game_id)
        if not game:
            return MoveResult(success=False, message="Game not found")
        if game.status == "finished":
            return MoveResult(success=False, message=f"Game over. Winner: {game.winner}", game_over=True,
                              winner=game.winner, winning_line=game.winning_line,
                              current_player=game.current_player)

        cell = game.grid[row][col]
        if cell.claimed_by is not None:
            return MoveResult(success=False, message="This square is already claimed.",
                              current_player=game.current_player)

        name = player_name.strip()
        if any(used.lower() == name.lower() for used in game.used_players):
            return self._turnover(game, f"Turnover! '{name}' was already picked this match.")

        index = self.index_for(game)
        candidates = index.catalog.find(name)
        if not candidates:
            return self._turnover(game, f"Turnover! '{name}' not found in {game.league} records.")

        row_spec = index.get(game.row_criteria[row].type.value, game.row_criteria[row].value)
        col_spec = index.get(game.col_criteria[col].type.value, game.col_criteria[col].value)
        # Same-named players: accept the one that fits the box, if any
        player = next((p for p in candidates if row_spec.matches(p) and col_spec.matches(p)), candidates[0])
        misses = [spec.miss for spec in (row_spec, col_spec) if not spec.matches(player)]
        if misses:
            return self._turnover(game, f"Turnover! {player['name']} {' and '.join(misses)}.")

        mover = game.current_player
        cell.claimed_by = mover
        cell.player_name = player["name"]
        cell.player_country = player.get("country", "")
        cell.player_teams = player.get("teams", [])
        game.used_players.append(player["name"])

        marks = [[c.claimed_by for c in grid_row] for grid_row in game.grid]
        line = winning_line(marks)
        if line:
            game.status, game.winner, game.winning_line = "finished", mover, line
            winner_name = game.player1_name if mover == "X" else game.player2_name
            return MoveResult(success=True, message=f"{winner_name} ({mover}) connects 3 in a row to win!",
                              game_over=True, winner=mover, winning_line=line, cell=cell,
                              current_player=game.current_player)
        if is_full(marks):
            game.status, game.winner = "finished", "DRAW"
            return MoveResult(success=True, message="Match Draw! All 9 boxes completed.", game_over=True,
                              winner="DRAW", cell=cell, current_player=game.current_player)

        game.current_player = other_player(mover)
        return MoveResult(success=True, message=f"{player['name']} confirmed for {row_spec.label} & {col_spec.label}.",
                          current_player=game.current_player, cell=cell)

    def answers(self, game_id: str, limit: int = 40) -> Optional[list]:
        """Every box's valid answers, best known first, once the game is over (None before)."""
        game = self.active_games.get(game_id)
        if not game or game.status != "finished":
            return None
        index = self.index_for(game)
        grid = []
        for r, row_crit in enumerate(game.row_criteria):
            row = []
            for c, col_crit in enumerate(game.col_criteria):
                players = index.answers(index.get(row_crit.type.value, row_crit.value),
                                        index.get(col_crit.type.value, col_crit.value))
                names = [p["name"] for p in sorted(players, key=lambda p: (-notability(p), p["name"]))]
                cell = game.grid[r][c]
                row.append({
                    "row": row_crit.display,
                    "col": col_crit.display,
                    "count": len(names),
                    "answers": names[:limit],
                    "picked": cell.player_name,
                    "claimed_by": cell.claimed_by,
                })
            grid.append(row)
        return grid

    def forfeit(self, game_id: str, loser: str) -> Optional[GameState]:
        """Ends a running game in the other player's favour (left or lost connection)."""
        game = self.active_games.get(game_id)
        if not game or game.status == "finished":
            return None
        game.status, game.winner = "finished", other_player(loser)
        return game

    def discard(self, game_id: str) -> None:
        self.active_games.pop(game_id, None)
        self.game_indexes.pop(game_id, None)
        self.created_at.pop(game_id, None)
        self.online_games.discard(game_id)

    def prune(self, max_age: float, keep=()) -> int:
        """Drops games older than max_age seconds, except those in keep; returns how many went."""
        now = time.monotonic()
        old = [gid for gid, created in self.created_at.items() if now - created > max_age and gid not in keep]
        for game_id in old:
            self.discard(game_id)
        return len(old)

    @staticmethod
    def _turnover(game: GameState, message: str) -> MoveResult:
        game.current_player = other_player(game.current_player)
        return MoveResult(success=False, message=message, current_player=game.current_player)

"""API models shared by the routes and the game manager."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Mark = Literal["X", "O"]
GridStyle = Literal["classic", "mixed", "custom"]
# Kinds a custom grid can mix with teams; which ones exist depends on the league
Category = Literal["country", "college", "draft", "award", "career", "era", "teammate"]
# How many well-known players fit each box (see backend/game/board.py)
Difficulty = Literal["easy", "medium", "hard"]
# Grids in a series; the first to win more than half takes it (drawn grids don't count)
BestOf = Literal[1, 3, 5, 7]


class CriterionType(str, Enum):
    TEAM = "team"
    COUNTRY = "country"
    COLLEGE = "college"
    DRAFT = "draft"
    AWARD = "award"
    CAREER = "career"
    ERA = "era"
    TEAMMATE = "teammate"


class Criterion(BaseModel):
    type: CriterionType
    value: str
    display: str


class Cell(BaseModel):
    row: int
    col: int
    claimed_by: Optional[Mark] = None
    player_name: Optional[str] = None
    player_country: Optional[str] = None
    player_teams: Optional[List[str]] = None


class NewGameRequest(BaseModel):
    league: Literal["nba", "euroleague"] = "nba"
    player1_name: str = Field("Player 1", max_length=24)
    player2_name: str = Field("Player 2", max_length=24)
    difficulty: Difficulty = "medium"
    shot_clock: Optional[int] = Field(60, ge=0, le=600)
    grid_style: GridStyle = "mixed"
    categories: Optional[List[Category]] = Field(None, max_length=7)  # custom grids only
    first_player: Mark = "X"


class CreateRoomRequest(BaseModel):
    league: Literal["nba", "euroleague"] = "nba"
    difficulty: Difficulty = "medium"
    shot_clock: int = Field(30, ge=0, le=600)
    grid_style: GridStyle = "mixed"
    categories: Optional[List[Category]] = Field(None, max_length=7)  # custom grids only
    best_of: BestOf = 3


class MoveRequest(BaseModel):
    game_id: str
    row: int = Field(ge=0, le=2)
    col: int = Field(ge=0, le=2)
    player_name: str = Field(max_length=80)
    # Which of several same-named players was picked (from the name list); optional
    player_key: Optional[str] = Field(None, max_length=120)


class GameRequest(BaseModel):
    """A same-device action on a whole game: shot clock violation, skipped turn, agreed draw."""
    game_id: str


class MoveResult(BaseModel):
    success: bool
    message: str
    game_over: bool = False
    winner: Optional[Literal["X", "O", "DRAW"]] = None
    winning_line: Optional[List[List[int]]] = None
    current_player: Mark = "X"
    cell: Optional[Cell] = None


class GameState(BaseModel):
    game_id: str
    league: str
    grid_style: GridStyle = "mixed"
    categories: Optional[List[str]] = None
    difficulty: Difficulty = "medium"
    shot_clock: Optional[int] = 60
    row_criteria: List[Criterion]
    col_criteria: List[Criterion]
    grid: List[List[Cell]]
    current_player: Mark
    player1_name: str = "Player 1"
    player2_name: str = "Player 2"
    status: Literal["in_progress", "finished"] = "in_progress"
    winner: Optional[Literal["X", "O", "DRAW"]] = None
    winning_line: Optional[List[List[int]]] = None
    used_players: List[str] = Field(default_factory=list)
    used_keys: List[str] = Field(default_factory=list)  # one per pick: tells same-named players apart

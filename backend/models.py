"""API models shared by the routes and the game manager."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Mark = Literal["X", "O"]
GridStyle = Literal["classic", "mixed"]


class CriterionType(str, Enum):
    TEAM = "team"
    COUNTRY = "country"
    COLLEGE = "college"
    DRAFT = "draft"
    AWARD = "award"
    CAREER = "career"
    ERA = "era"


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
    min_answers: int = Field(2, ge=1, le=4)
    shot_clock: Optional[int] = Field(60, ge=0, le=600)
    grid_style: GridStyle = "mixed"


class MoveRequest(BaseModel):
    game_id: str
    row: int = Field(ge=0, le=2)
    col: int = Field(ge=0, le=2)
    player_name: str = Field(max_length=80)


class ShotClockViolationRequest(BaseModel):
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
    min_answers: int = 2
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

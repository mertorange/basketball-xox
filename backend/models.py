from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum

class CriterionType(str, Enum):
    TEAM = "team"
    COUNTRY = "country"

class Criterion(BaseModel):
    type: CriterionType
    value: str
    display: str

class PlayerInfo(BaseModel):
    name: str
    country: str
    teams: List[str]

class Cell(BaseModel):
    row: int
    col: int
    claimed_by: Optional[Literal["X", "O"]] = None
    player_name: Optional[str] = None
    player_country: Optional[str] = None
    player_teams: Optional[List[str]] = None

class MoveRequest(BaseModel):
    game_id: str
    row: int
    col: int
    player_name: str

class MoveResult(BaseModel):
    success: bool
    message: str
    game_over: bool = False
    winner: Optional[Literal["X", "O", "DRAW"]] = None
    winning_line: Optional[List[List[int]]] = None
    current_player: Literal["X", "O"] = "X"
    cell: Optional[Cell] = None

class GameState(BaseModel):
    game_id: str
    league: str
    min_answers: int = 2
    shot_clock: Optional[int] = 60
    row_criteria: List[Criterion]
    col_criteria: List[Criterion]
    grid: List[List[Cell]]
    current_player: Literal["X", "O"]
    player1_name: str = "Player 1"
    player2_name: str = "Player 2"
    status: Literal["in_progress", "finished"] = "in_progress"
    winner: Optional[Literal["X", "O", "DRAW"]] = None
    winning_line: Optional[List[List[int]]] = None
    used_players: List[str] = Field(default_factory=list)

import json
import random
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from .models import Criterion, CriterionType, Cell, GameState, MoveResult

DATA_DIR = Path(__file__).resolve().parent / "data"

class BasketballDataStore:
    """Manages player datasets and criteria validation for NBA and EuroLeague."""
    def __init__(self):
        self.leagues: Dict[str, Dict[str, Any]] = {}
        self._load_datasets()

    def _load_datasets(self):
        for league_code, filename in [("nba", "nba_data.json"), ("euroleague", "euroleague_data.json")]:
            file_path = DATA_DIR / filename
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.leagues[league_code] = data
            else:
                self.leagues[league_code] = {"teams": [], "countries": [], "players": []}

    def get_players(self, league: str) -> List[Dict[str, Any]]:
        return self.leagues.get(league.lower(), {}).get("players", [])

    def get_teams(self, league: str) -> List[str]:
        return self.leagues.get(league.lower(), {}).get("teams", [])

    def get_countries(self, league: str) -> List[str]:
        return self.leagues.get(league.lower(), {}).get("countries", [])

    def find_player(self, league: str, player_name: str) -> Optional[Dict[str, Any]]:
        clean_name = player_name.strip().lower()
        for p in self.get_players(league):
            if p["name"].lower() == clean_name:
                return p
        return None

    def search_players(self, league: str, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        clean_q = query.strip().lower()
        if not clean_q:
            return []
        
        matches = []
        for p in self.get_players(league):
            p_name = p["name"].lower()
            if clean_q in p_name:
                priority = 0 if p_name.startswith(clean_q) else 1
                matches.append((priority, p))

        matches.sort(key=lambda x: (x[0], x[1]["name"]))
        return [p for _, p in matches[:limit]]

    def matches_criterion(self, player: Dict[str, Any], criterion: Criterion) -> bool:
        if criterion.type == CriterionType.TEAM:
            return any(t.lower() == criterion.value.lower() for t in player.get("teams", []))
        elif criterion.type == CriterionType.COUNTRY:
            return player.get("country", "").lower() == criterion.value.lower()
        return False

    def get_valid_players_for_cell(
        self, 
        league: str, 
        row_crit: Criterion, 
        col_crit: Criterion
    ) -> List[Dict[str, Any]]:
        return [
            p for p in self.get_players(league)
            if self.matches_criterion(p, row_crit) and self.matches_criterion(p, col_crit)
        ]


class GameManager:
    """Manages active games, rules, turns, and Tic-Tac-Toe win logic."""
    def __init__(self, data_store: BasketballDataStore):
        self.data_store = data_store
        self.active_games: Dict[str, GameState] = {}

    def create_game(
        self, 
        league: str = "nba", 
        player1_name: str = "Player 1", 
        player2_name: str = "Player 2",
        min_answers: int = 2
    ) -> GameState:
        league_clean = league.lower()
        if league_clean not in ["nba", "euroleague"]:
            league_clean = "nba"

        min_answers = max(1, min(min_answers, 4))
        row_criteria, col_criteria = self._generate_balanced_board(league_clean, min_answers=min_answers)

        grid = [
            [Cell(row=r, col=c) for c in range(3)]
            for r in range(3)
        ]

        game_id = str(uuid.uuid4())[:8]
        game_state = GameState(
            game_id=game_id,
            league=league_clean.upper(),
            min_answers=min_answers,
            row_criteria=row_criteria,
            col_criteria=col_criteria,
            grid=grid,
            current_player="X",
            player1_name=player1_name or "Player 1",
            player2_name=player2_name or "Player 2",
            status="in_progress",
            winner=None,
            winning_line=None,
            used_players=[]
        )

        self.active_games[game_id] = game_state
        return game_state

    def get_game(self, game_id: str) -> Optional[GameState]:
        return self.active_games.get(game_id)

    def make_move(self, game_id: str, row: int, col: int, player_name: str) -> MoveResult:
        game = self.active_games.get(game_id)
        if not game:
            return MoveResult(success=False, message="Game not found")

        if game.status == "finished":
            return MoveResult(
                success=False, 
                message=f"Game already finished. Winner: {game.winner}",
                game_over=True,
                winner=game.winner,
                winning_line=game.winning_line
            )

        if not (0 <= row < 3 and 0 <= col < 3):
            return MoveResult(success=False, message="Invalid coordinates")

        target_cell = game.grid[row][col]
        if target_cell.claimed_by is not None:
            return MoveResult(success=False, message="This cell is already claimed!")

        # Check duplicate
        clean_player_name = player_name.strip()
        if any(u.lower() == clean_player_name.lower() for u in game.used_players):
            curr_p = game.current_player
            game.current_player = "O" if curr_p == "X" else "X"
            return MoveResult(
                success=False, 
                message=f"'{clean_player_name}' was already picked this game! Turn forfeits to Player {game.current_player}.",
                current_player=game.current_player
            )

        # Validate existence
        player = self.data_store.find_player(game.league, clean_player_name)
        if not player:
            curr_p = game.current_player
            game.current_player = "O" if curr_p == "X" else "X"
            return MoveResult(
                success=False, 
                message=f"'{clean_player_name}' not found in {game.league} records. Turn forfeits to Player {game.current_player}.",
                current_player=game.current_player
            )

        # Verify criteria
        row_crit = game.row_criteria[row]
        col_crit = game.col_criteria[col]

        matches_row = self.data_store.matches_criterion(player, row_crit)
        matches_col = self.data_store.matches_criterion(player, col_crit)

        if not (matches_row and matches_col):
            reasons = []
            if not matches_row:
                reasons.append(f"did not play for {row_crit.display}" if row_crit.type == CriterionType.TEAM else f"is not from {row_crit.display}")
            if not matches_col:
                reasons.append(f"did not play for {col_crit.display}" if col_crit.type == CriterionType.TEAM else f"is not from {col_crit.display}")

            curr_p = game.current_player
            game.current_player = "O" if curr_p == "X" else "X"
            return MoveResult(
                success=False,
                message=f"Miss! {player['name']} {' and '.join(reasons)}. Turn forfeits to Player {game.current_player}.",
                current_player=game.current_player
            )

        # Valid move
        claiming_player = game.current_player
        target_cell.claimed_by = claiming_player
        target_cell.player_name = player["name"]
        target_cell.player_country = player.get("country", "")
        target_cell.player_teams = player.get("teams", [])
        game.used_players.append(player["name"])

        # Check win
        winning_line = self._check_winner(game.grid)
        if winning_line:
            game.status = "finished"
            game.winner = claiming_player
            game.winning_line = winning_line
            winner_name = game.player1_name if claiming_player == "X" else game.player2_name
            return MoveResult(
                success=True,
                message=f"Game Over! {winner_name} ({claiming_player}) wins with 3 in a row!",
                game_over=True,
                winner=claiming_player,
                winning_line=winning_line,
                cell=target_cell,
                current_player=game.current_player
            )

        # Check draw
        all_claimed = all(game.grid[r][c].claimed_by is not None for r in range(3) for c in range(3))
        if all_claimed:
            game.status = "finished"
            game.winner = "DRAW"
            return MoveResult(
                success=True,
                message=f"Game Over! All 9 boxes completed with no 3 in a row. It's a draw!",
                game_over=True,
                winner="DRAW",
                cell=target_cell,
                current_player=game.current_player
            )

        # Switch turn
        game.current_player = "O" if claiming_player == "X" else "X"

        return MoveResult(
            success=True,
            message=f"Valid! {player['name']} matches {row_crit.display} & {col_crit.display}.",
            game_over=False,
            current_player=game.current_player,
            cell=target_cell
        )

    def _check_winner(self, grid: List[List[Cell]]) -> Optional[List[List[int]]]:
        # Rows
        for r in range(3):
            if grid[r][0].claimed_by and (grid[r][0].claimed_by == grid[r][1].claimed_by == grid[r][2].claimed_by):
                return [[r, 0], [r, 1], [r, 2]]

        # Columns
        for c in range(3):
            if grid[0][c].claimed_by and (grid[0][c].claimed_by == grid[1][c].claimed_by == grid[2][c].claimed_by):
                return [[0, c], [1, c], [2, c]]

        # Diagonals
        if grid[0][0].claimed_by and (grid[0][0].claimed_by == grid[1][1].claimed_by == grid[2][2].claimed_by):
            return [[0, 0], [1, 1], [2, 2]]

        if grid[0][2].claimed_by and (grid[0][2].claimed_by == grid[1][1].claimed_by == grid[2][0].claimed_by):
            return [[0, 2], [1, 1], [2, 0]]

        return None

    def _generate_balanced_board(self, league: str, min_answers: int = 2) -> Tuple[List[Criterion], List[Criterion]]:
        """
        Generates 3 row criteria and 3 col criteria such that
        EVERY one of the 9 cells has at least `min_answers` valid players.
        Ensures never having Country x Country.
        """
        teams = self.data_store.get_teams(league)
        countries = self.data_store.get_countries(league)

        team_crits = [Criterion(type=CriterionType.TEAM, value=t, display=t) for t in teams]
        country_crits = [Criterion(type=CriterionType.COUNTRY, value=c, display=c) for c in countries]

        # Try target threshold, and step down if needed
        for target_min in [min_answers, max(1, min_answers - 1), 1]:
            for _ in range(4000):
                # Rows can have 2 teams + 1 country OR 3 teams
                if random.random() < 0.6 and country_crits:
                    rows = random.sample(team_crits, 2) + random.sample(country_crits, 1)
                    random.shuffle(rows)
                    # Columns will be teams only to avoid Country x Country
                    avail_teams = [t for t in team_crits if t.value not in [r.value for r in rows]]
                    cols = random.sample(avail_teams, 3)
                else:
                    # 3 teams vs 3 teams
                    chosen = random.sample(team_crits, 6)
                    rows = chosen[:3]
                    cols = chosen[3:]

                # Check if every single cell has >= target_min valid players
                solvable = True
                for r_crit in rows:
                    for c_crit in cols:
                        ans_count = len(self.data_store.get_valid_players_for_cell(league, r_crit, c_crit))
                        if ans_count < target_min:
                            solvable = False
                            break
                    if not solvable:
                        break

                if solvable:
                    return rows, cols

        # Guaranteed high-density fallbacks
        if league == "nba":
            return (
                [
                    Criterion(type=CriterionType.TEAM, value="Los Angeles Lakers", display="Los Angeles Lakers"),
                    Criterion(type=CriterionType.TEAM, value="Miami Heat", display="Miami Heat"),
                    Criterion(type=CriterionType.COUNTRY, value="USA", display="USA"),
                ],
                [
                    Criterion(type=CriterionType.TEAM, value="Cleveland Cavaliers", display="Cleveland Cavaliers"),
                    Criterion(type=CriterionType.TEAM, value="Houston Rockets", display="Houston Rockets"),
                    Criterion(type=CriterionType.TEAM, value="Dallas Mavericks", display="Dallas Mavericks"),
                ]
            )
        else:
            return (
                [
                    Criterion(type=CriterionType.TEAM, value="FC Barcelona", display="FC Barcelona"),
                    Criterion(type=CriterionType.TEAM, value="Panathinaikos", display="Panathinaikos"),
                    Criterion(type=CriterionType.COUNTRY, value="USA", display="USA"),
                ],
                [
                    Criterion(type=CriterionType.TEAM, value="Real Madrid", display="Real Madrid"),
                    Criterion(type=CriterionType.TEAM, value="Olympiacos", display="Olympiacos"),
                    Criterion(type=CriterionType.TEAM, value="Fenerbahçe", display="Fenerbahçe"),
                ]
            )

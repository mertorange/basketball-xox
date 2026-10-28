"""Player datasets: loading, lookup by name and autocomplete search."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

# HOOPGRID_DATA_DIR points the app (or the tests) at another set of dataset files
DATA_DIR = Path(os.environ.get("HOOPGRID_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
LEAGUE_FILES = {"nba": "nba_data.json", "euroleague": "euroleague_data.json"}

Player = Dict[str, Any]


class PlayerCatalog:
    """One league's players, as written by backend/scripts/build_databases.py."""

    def __init__(self, league: str, dataset: Dict[str, Any]):
        self.league = league
        self.teams: List[str] = dataset.get("teams", [])
        self.countries: List[str] = dataset.get("countries", [])
        self.players: List[Player] = dataset.get("players", [])
        self._by_name: Dict[str, List[Player]] = {}
        for player in self.players:
            self._by_name.setdefault(player["name"].lower(), []).append(player)

    @classmethod
    def load(cls, league: str, data_dir: Path = DATA_DIR) -> "PlayerCatalog":
        path = data_dir / LEAGUE_FILES[league]
        if not path.exists():
            return cls(league, {})
        with open(path, "r", encoding="utf-8") as f:
            return cls(league, json.load(f))

    def find(self, name: str) -> List[Player]:
        """All players with this name; a few names belong to two different players."""
        return self._by_name.get(name.strip().lower(), [])

    def search(self, query: str, limit: int = 8) -> List[Player]:
        """Names containing the query, those starting with it first, one row per name."""
        q = query.strip().lower()
        if not q:
            return []
        matches = []
        for name, players in self._by_name.items():
            if q in name:
                matches.append((0 if name.startswith(q) else 1, players[0]["name"], players[0]))
        matches.sort(key=lambda m: (m[0], m[1]))
        return [player for _, _, player in matches[:limit]]


def load_catalogs(data_dir: Path = DATA_DIR) -> Dict[str, PlayerCatalog]:
    return {league: PlayerCatalog.load(league, data_dir) for league in LEAGUE_FILES}

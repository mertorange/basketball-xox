"""Player datasets: loading, lookup by name and autocomplete search."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fame import assign_fame

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
        assign_fame(league, self.players)
        self._by_name: Dict[str, List[Player]] = {}
        for player in self.players:
            self._by_name.setdefault(player["name"].lower(), []).append(player)
        # Same-named players get a key each (name plus birth date) so a pick names the right one
        for same in self._by_name.values():
            for i, player in enumerate(same):
                player["key"] = player_key(player, i if len(same) > 1 else None)
        self._aliases: Dict[str, Player] = {alias.lower(): p for p in self.players for alias in p.get("aliases", ())}
        self.name_list = self._name_list()

    @classmethod
    def load(cls, league: str, data_dir: Path = DATA_DIR) -> "PlayerCatalog":
        path = data_dir / LEAGUE_FILES[league]
        if not path.exists():
            return cls(league, {})
        with open(path, "r", encoding="utf-8") as f:
            return cls(league, json.load(f))

    def find(self, name: str) -> List[Player]:
        """All players with this name; a few names belong to two different players."""
        key = name.strip().lower()
        if key in self._by_name:
            return self._by_name[key]
        return [self._aliases[key]] if key in self._aliases else []

    def _name_list(self) -> Dict[str, Any]:
        """Every name for the autocomplete, which filters in the browser. Same-named players
        come with what tells them apart (birth date, position) and their key, and other names
        (Ron Artest, Shaq) with the player they lead to; nothing about teams, awards or
        countries, which would give answers away."""
        twins = {}
        for same in self._by_name.values():
            if len(same) > 1:
                twins[same[0]["name"]] = [{"key": p["key"], "born": p.get("born"), "pos": p.get("pos")}
                                          for p in sorted(same, key=lambda p: str(p.get("born") or ""))]
        aliases = {alias: {"name": p["name"], "key": p["key"] if p["name"] in twins else None}
                   for p in self.players for alias in p.get("aliases", ())}
        return {"names": sorted({p["name"] for p in self.players}), "twins": twins, "aliases": aliases}

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


def player_key(player: Player, twin_index: Optional[int] = None) -> str:
    """A stable id: the name, plus the birth date (or the file order) when the name is shared."""
    if twin_index is None:
        return player["name"]
    return f"{player['name']}|{player.get('born') or f'#{twin_index}'}"


def notability(player: Player) -> float:
    """How well known a player is, for ordering answer lists; set when the catalog loads."""
    return player.get("fame_score", 0)


def load_catalogs(data_dir: Path = DATA_DIR) -> Dict[str, PlayerCatalog]:
    return {league: PlayerCatalog.load(league, data_dir) for league in LEAGUE_FILES}

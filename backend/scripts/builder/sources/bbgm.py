"""Basketball GM community roster snapshots (github.com/alexnoob/BasketBall-GM-Rosters).

Each file is one season's league: teams, players (birth, college, draft, current team and,
from 2019-20 on, a stats history with mid-season moves and playoff runs) and, from 2022-23
on, the league's full award and playoff history back to 1947.
"""

import urllib.parse
from dataclasses import dataclass, field

from ..common import http_get, parse_json_lenient
from ..nba_teams import TEAM_NAME_NORMALIZER

NBA_ROSTER_BASE = "https://raw.githubusercontent.com/alexnoob/BasketBall-GM-Rosters/master/"
NBA_ROSTER_FILES = ["1995-96.NBA.Roster.json", "2009-10 Rosters.json"] + [
    f"{y}-{str(y + 1)[-2:]}.NBA.Roster.json" for y in range(2015, 2026)
]

# Birth years in this file are shifted by about nine years and most birthplaces are
# college names, so births come from FiveThirtyEight and countries from fallbacks.
NBA_ROSTERS_WITH_BAD_BIOS = {"2009-10 Rosters.json"}

# League award keys -> the award names used in the dataset
LEAGUE_AWARDS = {
    "mvp": "mvp",
    "finalsMvp": "finals_mvp",
    "roy": "roy",
    "dpoy": "dpoy",
    "smoy": "sixth_man",
    "mip": "mip",
}


@dataclass
class Snapshot:
    filename: str
    season: int                      # the year the season ends: 2025-26 -> 2026
    teams: dict                      # tid -> current franchise name
    players: list
    awards: list = field(default_factory=list)          # league award history, newest files only
    playoff_series: list = field(default_factory=list)  # playoff brackets, newest files only

    @property
    def unreliable_bios(self):
        return self.filename in NBA_ROSTERS_WITH_BAD_BIOS


def load_snapshots():
    snapshots = []
    for filename in NBA_ROSTER_FILES:
        print(f"Fetching NBA roster: {filename} ...")
        text = http_get(NBA_ROSTER_BASE + urllib.parse.quote(filename))
        if text is None:
            print("  Not found, skipped")
            continue
        data = parse_json_lenient(text)
        teams = {}
        for t in data.get("teams", []):
            full = f"{t.get('region', '')} {t.get('name', '')}".strip()
            franchise = TEAM_NAME_NORMALIZER.get(full.lower()) or TEAM_NAME_NORMALIZER.get(t.get("name", "").lower())
            if franchise:
                teams[t.get("tid")] = franchise
        snapshots.append(Snapshot(
            filename=filename,
            season=data.get("startingSeason") or int(filename[:4]) + 1,
            teams=teams,
            players=data.get("players", []),
            awards=data.get("awards") or [],
            playoff_series=data.get("playoffSeries") or [],
        ))
    return snapshots


def champions_by_season(snapshot):
    """Season -> champion franchise, from a snapshot's playoff history (finals winner)."""
    champions = {}
    for entry in snapshot.playoff_series:
        rounds = entry.get("series") or []
        if not rounds or not rounds[-1]:
            continue
        final = rounds[-1][0]
        home, away = final.get("home") or {}, final.get("away") or {}
        winner = home if home.get("won", 0) > away.get("won", 0) else away
        franchise = snapshot.teams.get(winner.get("tid"))
        if franchise and home.get("won") != away.get("won"):
            champions[entry["season"]] = franchise
    return champions


def league_award_winners(snapshot):
    """Yields (season, award, winner name, franchise or None) from the league history."""
    for entry in snapshot.awards:
        season = entry.get("season")
        for key, award in LEAGUE_AWARDS.items():
            winner = entry.get(key)
            if winner and winner.get("name"):
                yield season, award, winner["name"], snapshot.teams.get(winner.get("tid"))
        for team in entry.get("allLeague") or []:
            for winner in team.get("players") or []:
                if winner.get("name"):
                    yield season, "all_nba", winner["name"], snapshot.teams.get(winner.get("tid"))

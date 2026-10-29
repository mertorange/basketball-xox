"""FiveThirtyEight player-season table, 1977-2020 (CC BY 4.0)."""

import csv
import io
from collections import defaultdict

from ..common import base_name_key, http_get
from ..nba_teams import BREF_TEAM_TO_FRANCHISE

FIVETHIRTYEIGHT_URL = (
    "https://raw.githubusercontent.com/fivethirtyeight/nba-player-advanced-metrics/master/nba-data-historical.csv"
)
FIVETHIRTYEIGHT_FIRST_SEASON = 1977


def load_fivethirtyeight():
    """Returns (career, season_births, players, workload) from FiveThirtyEight's table.

    career: (base name, possible birth year) -> {player_id: {(season, franchise, playoffs)}}
    season_births: (base name, season) -> {player_id: birth year}
    players: player_id -> (name, birth year, {(season, franchise, playoffs)})
    workload: player_id -> {(season, franchise): (games, minutes)}, regular season only;
              also player_id -> "pos" for the position in the latest season
    """
    print("Fetching FiveThirtyEight player-season history ...")
    career = defaultdict(lambda: defaultdict(set))
    season_births = defaultdict(dict)
    players = {}
    workload = defaultdict(dict)
    for row in csv.DictReader(io.StringIO(http_get(FIVETHIRTYEIGHT_URL))):
        team = BREF_TEAM_TO_FRANCHISE.get(row["team_id"])
        if not team or not row["age"].isdigit():
            continue
        base = base_name_key(row["name_common"])
        season = int(row["year_id"])
        # Ages are taken on Feb 1 of the season, so the birth year is one of two
        birth_year = season - int(row["age"])
        stint = (season, team, row["type"] == "PO")
        for year in (birth_year - 1, birth_year):
            career[(base, year)][row["player_id"]].add(stint)
        season_births[(base, season)][row["player_id"]] = birth_year - 1
        entry = players.setdefault(row["player_id"], (row["name_common"], birth_year - 1, set()))
        entry[2].add(stint)
        if row["pos"] and row["pos"] != "NULL":
            workload[row["player_id"]]["pos"] = max(workload[row["player_id"]].get("pos", (0, "")),
                                                     (season, row["pos"]))
        if row["type"] == "RS" and row["G"].isdigit():
            minutes = int(row["Min"]) if row["Min"].isdigit() else 0
            workload[row["player_id"]][(season, team)] = (int(row["G"]), minutes)
    return career, season_births, players, workload

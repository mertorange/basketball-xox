"""Fame: how well known a player is in their league, as a percentile from 0 to 100.

The datasets hold facts; this turns them into one number per player when a catalog loads,
so the formula can be tuned without rebuilding the data. Grid difficulty counts the
well-known answers in each box (see backend/game/board.py).

NBA: how many Wikimedia pages the player has (Wikidata sitelinks: an MVP has dozens, a
short stint one or two), career regular-season minutes since 1977, awards weighted by how
memorable they are, and a top draft slot (so this year's #1 pick counts before he plays).
Pages carry the most weight: they also cover players before 1977, who have no minutes.
A player Wikidata could not be matched to gets the usual page count of players with as
many minutes.

EuroLeague: only what the player did in the EuroLeague (points and games since 2000-01,
titles, Final Fours). Wikipedia would favour players from countries with many language
editions and players known for the NBA or a national team. A few famous names the stats
miss are listed by hand.
"""

import math
from collections import defaultdict
from statistics import median
from typing import Dict, List

# Percentile from which a player counts as well known: about the top 500 in the NBA,
# the top 350 in the EuroLeague
WELL_KNOWN = {"nba": 90, "euroleague": 85}

NBA_AWARD_POINTS = {
    "mvp": 4.0, "finals_mvp": 3.0, "all_nba": 3.0, "dpoy": 2.0, "roy": 2.0,
    "sixth_man": 1.0, "mip": 1.0, "champion": 1.0,
}
EUROLEAGUE_AWARD_POINTS = {"champion": 2.0, "final_four": 1.0}

# Well known, but the EuroLeague stats (2000-01 on) don't show it
EUROLEAGUE_FAMOUS = {
    "Sarunas Jasikevicius", "Zeljko Rebraca",                # mostly before 2000-01, no stats kept
    "Alphonso Ford",                                         # top scorer whose prime was the 1990s
    "Andrei Kirilenko",                                      # one season, the 2012 MVP one
}


def _pages_by_minutes(players: List[Dict]) -> Dict[int, float]:
    """Median page count of the players Wikidata knows, by career-minutes band."""
    bands = defaultdict(list)
    for p in players:
        if "wiki_pages" in p:
            bands[_minutes_band(p)].append(p["wiki_pages"])
    return {band: median(pages) for band, pages in bands.items()}


def _minutes_band(player: Dict) -> int:
    return int(math.log2(1 + (player.get("stats") or {}).get("minutes", 0)))


def nba_score(player: Dict, typical_pages: Dict[int, float]) -> float:
    stats = player.get("stats") or {}
    pages = player.get("wiki_pages", typical_pages.get(_minutes_band(player), 0))
    draft = player.get("draft") or {}
    top_pick = draft.get("round") == 1 and 1 <= draft.get("pick", 0) <= 10
    return (2.5 * math.log1p(pages)
            + 0.5 * math.log1p(stats.get("minutes", 0) / 100)
            + sum(NBA_AWARD_POINTS.get(a, 0) for a in player.get("awards", ()))
            + (2.0 if top_pick and draft["pick"] == 1 else 0.75 if top_pick else 0))


def euroleague_score(player: Dict, _=None) -> float:
    if player["name"] in EUROLEAGUE_FAMOUS:
        return math.inf
    stats = player.get("stats") or {}
    return (2.0 * math.log1p(stats.get("points", 0)) + 1.0 * math.log1p(stats.get("games", 0))
            + sum(EUROLEAGUE_AWARD_POINTS.get(a, 0) for a in player.get("awards", ())))


def assign_fame(league: str, players: List[Dict]) -> None:
    """Sets player["fame"]: the share of the league's players scoring below them, 0-100,
    and player["fame_score"]: the raw score, which keeps the order among the top 1%."""
    if league == "nba":
        typical = _pages_by_minutes(players)
        scores = [nba_score(p, typical) for p in players]
    else:
        scores = [euroleague_score(p) for p in players]
    ranked = sorted(scores)
    n = max(len(players) - 1, 1)
    # Equal scores share a percentile: the position of the first of them
    first = {}
    for i, s in enumerate(ranked):
        first.setdefault(s, i)
    for player, s in zip(players, scores):
        player["fame"] = round(100 * first[s] / n)
        player["fame_score"] = s


def is_well_known(league: str, player: Dict) -> bool:
    return player.get("fame", 0) >= WELL_KNOWN.get(league, 90)

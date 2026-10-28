"""Official EuroLeague API (api-live.euroleague.net)."""

import json
import re
from collections import defaultdict
from datetime import date

from ..common import canonical_country, clean_player_name, http_get, name_key
from ..euroleague_clubs import normalize_euroleague_club

# The API returns 500 records unless asked for more (2001-02 has 527 registrations)
EUROLEAGUE_PEOPLE_URL = (
    "https://api-live.euroleague.net/v2/competitions/E/seasons/E{season}/people?personType=J&limit=2000"
)

EUROLEAGUE_SEASON_URL = "https://api-live.euroleague.net/v2/competitions/E/seasons/E{season}"
EUROLEAGUE_GAMES_URL = "https://api-live.euroleague.net/v2/competitions/E/seasons/E{season}/games"
# Accumulated totals for every player over a season range, in one call
EUROLEAGUE_CAREER_URL = (
    "https://api-live.euroleague.net/v3/competitions/E/statistics/players/traditional"
    "?SeasonMode=Range&FromSeasonCode=E{first}&ToSeasonCode=E{last}&statisticMode=Accumulated&limit=10000"
)

EUROLEAGUE_FIRST_SEASON = 2000


def euroleague_seasons():
    """Season start years from 2000-01 to the current one."""
    return range(EUROLEAGUE_FIRST_SEASON, date.today().year + 1)

def format_euroleague_name(raw_name):
    """'MCCORMACK, DAVID' -> 'David McCormack'."""
    parts = raw_name.split(",", 1)
    name = f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else raw_name
    name = clean_player_name(name).title()
    name = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), name)
    name = re.sub(r"\b(Ii|Iii|Iv)\b", lambda m: m.group(1).upper(), name)
    return re.sub(r"\bJr\b\.?", "Jr.", name)

_euroleague_people = None

def fetch_euroleague_people():
    """All EuroLeague player registrations since 2000-01, grouped per person (cached)."""
    global _euroleague_people
    if _euroleague_people is not None:
        return _euroleague_people

    # (name_key, birth date) -> collected facts; player codes are stable but a few
    # players were registered under two codes
    people = {}
    keys_by_name = defaultdict(list)

    for season in euroleague_seasons():
        text = http_get(EUROLEAGUE_PEOPLE_URL.format(season=season))
        payload = json.loads(text) if text else {}
        rows = payload.get("data") or []
        if (payload.get("total") or 0) > len(rows):
            print(f"  WARNING: only {len(rows)} of {payload['total']} registrations returned")
        print(f"EuroLeague {season}-{str(season + 1)[-2:]}: {len(rows)} player registrations")
        for row in rows:
            person = row.get("person") or {}
            raw_name = (person.get("name") or "").strip()
            club = normalize_euroleague_club((row.get("club") or {}).get("name"))
            if len(raw_name) < 3 or not club:
                continue
            name = format_euroleague_name(raw_name)
            birth_date = (person.get("birthDate") or "")[:10]
            if birth_date:
                key = (name_key(name), birth_date)
            else:
                # No birth date: attach to the only same-named player if there is one
                same_name = keys_by_name[name_key(name)]
                key = same_name[0] if len(same_name) == 1 else (name_key(name), person.get("code"))
            if key not in people:
                people[key] = {"names": [], "clubs": set(), "countries": [], "seasons": set(), "codes": set(),
                               "born": int(birth_date[:4]) if birth_date else None}
                keys_by_name[key[0]].append(key)
            entry = people[key]
            entry["names"].append((season, name))
            entry["clubs"].add(club)
            entry["seasons"].add((season, club))
            if person.get("code"):
                entry["codes"].add(person["code"])
            # Birth country first: the registered nationality is often a second passport
            # (Ginobili and Scola are listed as Italian and Spanish)
            country = (canonical_country((person.get("birthCountry") or {}).get("name"))
                       or canonical_country((person.get("country") or {}).get("name")))
            if country:
                entry["countries"].append((season, country))

    _euroleague_people = people
    return people


def fetch_champions():
    """Season start year -> champion club (2019-20 was cancelled and has none)."""
    champions = {}
    for season in euroleague_seasons():
        text = http_get(EUROLEAGUE_SEASON_URL.format(season=season))
        winner = (json.loads(text).get("winner") or {}) if text else {}
        if winner.get("name"):
            champions[season] = normalize_euroleague_club(winner["name"])
    print(f"  EuroLeague champions for {len(champions)} seasons")
    return champions


def fetch_final_four_clubs():
    """Season start year -> clubs that played the Final Four."""
    clubs = defaultdict(set)
    for season in euroleague_seasons():
        text = http_get(EUROLEAGUE_GAMES_URL.format(season=season))
        payload = json.loads(text) if text else {}
        for game in payload.get("data", []) if isinstance(payload, dict) else payload:
            if (game.get("phaseType") or {}).get("code") != "FF":
                continue
            for side in ("local", "road"):
                club = ((game.get(side) or {}).get("club") or {}).get("name")
                if club:
                    clubs[season].add(normalize_euroleague_club(club))
    print(f"  Final Four clubs for {len(clubs)} seasons")
    return clubs


def fetch_career_stats():
    """Player code -> EuroLeague career totals: games, points, rebounds, assists."""
    seasons = euroleague_seasons()
    text = http_get(EUROLEAGUE_CAREER_URL.format(first=seasons[0], last=seasons[-1]))
    payload = json.loads(text) if text else {}
    totals = {}
    for row in payload.get("players", []):
        code = (row.get("player") or {}).get("code")
        if code:
            totals[code] = {
                "games": int(row.get("gamesPlayed") or 0),
                "points": int(row.get("pointsScored") or 0),
                "rebounds": int(row.get("totalRebounds") or 0),
                "assists": int(row.get("assists") or 0),
            }
    print(f"  Career totals for {len(totals)} players")
    return totals

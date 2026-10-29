"""ESPN's public roster feed: the current season.

The community snapshots lag a season behind: summer signings such as Marcus Smart to
Houston in July 2026 are missing from them.
"""

import json
from dataclasses import dataclass

from ..common import clean_player_name, http_get
from ..nba_teams import TEAM_NAME_NORMALIZER

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"


@dataclass
class EspnPlayer:
    season: int
    name: str
    born: int
    birthplace: str  # 'City, ST' for Americans, 'City, Country' otherwise, like the snapshots
    team: str
    college: str
    dob: str = ""        # YYYY-MM-DD
    position: str = ""   # 'PG', 'F', ...


def load_espn_rosters():
    print("Fetching current NBA rosters from ESPN ...")
    teams = json.loads(http_get(ESPN_TEAMS_URL))["sports"][0]["leagues"][0]["teams"]
    players = []
    for item in teams:
        team = TEAM_NAME_NORMALIZER.get(item["team"]["displayName"].lower())
        if not team:
            print(f"  Unknown ESPN team {item['team']['displayName']!r}, skipped")
            continue
        roster = json.loads(http_get(ESPN_ROSTER_URL.format(team_id=item["team"]["id"])))
        season = (roster.get("season") or {}).get("year")
        for athlete in roster.get("athletes", []):
            born = athlete.get("dateOfBirth", "")[:4]
            name = clean_player_name(athlete.get("fullName", ""))
            if len(name) < 3 or not born.isdigit():
                continue
            place = athlete.get("birthPlace") or {}
            region = place.get("state") if place.get("country") == "USA" and place.get("state") else place.get("country")
            players.append(EspnPlayer(
                season=season,
                name=name,
                born=int(born),
                birthplace=f"{place.get('city', '')}, {region}" if region else "",
                team=team,
                college=(athlete.get("college") or {}).get("name", ""),
                dob=athlete.get("dateOfBirth", "")[:10],
                position=(athlete.get("position") or {}).get("abbreviation", ""),
            ))
    print(f"  {len(players)} players on {len(teams)} rosters")
    return players

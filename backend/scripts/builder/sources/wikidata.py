"""Wikidata SPARQL: NBA franchise members, birth countries and pre-1977 stints (CC0).

Undated memberships mix in coaching jobs (Phil Jackson 'joins' the Bulls), and the Pelicans
item also carries some 1988-2002 Charlotte Hornets stints, so Wikidata teams are only
trusted for the years before FiveThirtyEight's coverage starts.
"""

import json
import urllib.parse

from ..common import canonical_country, clean_player_name, http_get
from ..nba_teams import WIKIDATA_NBA_TEAMS

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

BASKETBALL_COACH = "Q5137571"

# Listed as players and as members of an NBA team, but the stint was a coaching job
NOT_NBA_PLAYERS = {"Ettore Messina"}

WIKIDATA_QUERY = """
SELECT ?p ?pLabel ?dob ?team ?start ?end ?countryLabel ?coach WHERE {
  VALUES ?team { %s }
  ?p p:P54 ?st . ?st ps:P54 ?team .
  ?p wdt:P31 wd:Q5 ; wdt:P106 wd:Q3665646 .  # basketball players, not coaches or executives
  OPTIONAL { ?st pq:P580 ?start }
  OPTIONAL { ?st pq:P582 ?end }
  OPTIONAL { ?p wdt:P569 ?dob }
  OPTIONAL {
    ?p wdt:P19 ?pob . ?pob wdt:P17 ?country .
    FILTER NOT EXISTS { ?country wdt:P576 ?dissolved }
    ?country rdfs:label ?countryLabel FILTER(LANG(?countryLabel) = "en")
  }
  BIND(EXISTS { ?p wdt:P106 wd:%s } AS ?coach)
  ?p rdfs:label ?pLabel FILTER(LANG(?pLabel) = "en")
}
""" % (" ".join("wd:" + q for q in WIKIDATA_NBA_TEAMS), BASKETBALL_COACH)

def load_wikidata_players():
    """NBA franchise members from Wikidata with birth year, birth country and team stints."""
    print("Querying Wikidata for NBA players ...")
    url = WIKIDATA_SPARQL_URL + "?" + urllib.parse.urlencode({"query": WIKIDATA_QUERY, "format": "json"})
    # The query runs close to Wikidata's time limit; a cut-off response is retried
    for attempt in range(3):
        try:
            rows = json.loads(http_get(url), strict=False)["results"]["bindings"]
            break
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            print("  Incomplete response, retrying ...")
    players = {}
    for row in rows:
        qid = row["p"]["value"].rsplit("/", 1)[1]
        dob = row.get("dob", {}).get("value", "")
        entry = players.setdefault(qid, {
            "name": clean_player_name(row["pLabel"]["value"]),
            "born": int(dob[:4]) if dob[:4].isdigit() else None,
            "countries": set(), "dated": set(), "undated": set(),
            "coach": row["coach"]["value"] == "true",
        })
        team = WIKIDATA_NBA_TEAMS[row["team"]["value"].rsplit("/", 1)[1]]
        start = row.get("start", {}).get("value", "")[:4]
        end = row.get("end", {}).get("value", "")[:4]
        if start.isdigit():
            if team == "New Orleans Pelicans" and int(start) < 2002:
                team = "Charlotte Hornets"
            entry["dated"].add((int(start), int(end) if end.isdigit() else None, team))
        else:
            entry["undated"].add(team)
        if "countryLabel" in row:
            entry["countries"].add(canonical_country(row["countryLabel"]["value"]))
    players = {qid: e for qid, e in players.items() if e["name"] not in NOT_NBA_PLAYERS}
    for entry in players.values():
        # A few birthplaces list several current countries (or a US state); USA wins ties
        countries = entry.pop("countries")
        entry["country"] = "USA" if "USA" in countries else (min(countries) if countries else None)
    print(f"  {len(players)} players")
    return players

def wikidata_teams(entry, before=None, include_undated=True):
    """Franchises from Wikidata stints; undated stints count only for non-coaches."""
    teams = {team for start, _, team in entry["dated"] if before is None or start < before}
    if include_undated and not entry["coach"]:
        undated = set(entry["undated"])
        if "New Orleans Pelicans" in undated and (entry["born"] or 0) < 1975:
            undated.discard("New Orleans Pelicans")
            # Born before 1965: retired before the 2002 move, so a Charlotte-era stint
            if entry["born"] and entry["born"] < 1965:
                undated.add("Charlotte Hornets")
        teams |= undated
    return teams


def wikidata_seasons(entry, before=None):
    """(season, franchise) pairs from dated stints with an end year.

    Start years are usually the signing year, so the first season played is the one that
    ends the following spring: a 1959-2001 stint covers the 1960 ... 2001 seasons.
    """
    seasons = set()
    for start, end, team in entry["dated"]:
        if end is None:
            continue
        for season in range(start + 1, end + 1):
            if before is None or season < before:
                seasons.add((season, team))
    return seasons

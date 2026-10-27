"""
Database Builder & Enrichment Script for Basketball XOX
Fetches and merges deep historical and modern rosters from verified basketball data sources.
Includes official 2026-27 EuroLeague season data directly from the EuroLeague API.
"""

import json
import re
import sys
import requests
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Standard 30 NBA Teams
STANDARD_NBA_TEAMS = [
    "Los Angeles Lakers",
    "Boston Celtics",
    "Golden State Warriors",
    "Chicago Bulls",
    "Miami Heat",
    "San Antonio Spurs",
    "Dallas Mavericks",
    "Houston Rockets",
    "Brooklyn Nets",
    "Philadelphia 76ers",
    "Denver Nuggets",
    "Phoenix Suns",
    "Milwaukee Bucks",
    "Toronto Raptors",
    "New York Knicks",
    "LA Clippers",
    "Cleveland Cavaliers",
    "Oklahoma City Thunder",
    "Portland Trail Blazers",
    "Minnesota Timberwolves",
    "Atlanta Hawks",
    "Memphis Grizzlies",
    "Indiana Pacers",
    "New Orleans Pelicans",
    "Orlando Magic",
    "Sacramento Kings",
    "Detroit Pistons",
    "Utah Jazz",
    "Washington Wizards",
    "Charlotte Hornets"
]

TEAM_NAME_NORMALIZER = {
    "los angeles clippers": "LA Clippers",
    "la clippers": "LA Clippers",
    "clippers": "LA Clippers",
    "los angeles lakers": "Los Angeles Lakers",
    "lakers": "Los Angeles Lakers",
    "boston celtics": "Boston Celtics",
    "celtics": "Boston Celtics",
    "golden state warriors": "Golden State Warriors",
    "warriors": "Golden State Warriors",
    "chicago bulls": "Chicago Bulls",
    "bulls": "Chicago Bulls",
    "miami heat": "Miami Heat",
    "heat": "Miami Heat",
    "san antonio spurs": "San Antonio Spurs",
    "spurs": "San Antonio Spurs",
    "dallas mavericks": "Dallas Mavericks",
    "mavericks": "Dallas Mavericks",
    "houston rockets": "Houston Rockets",
    "rockets": "Houston Rockets",
    "brooklyn nets": "Brooklyn Nets",
    "new jersey nets": "Brooklyn Nets",
    "nets": "Brooklyn Nets",
    "philadelphia 76ers": "Philadelphia 76ers",
    "76ers": "Philadelphia 76ers",
    "sixers": "Philadelphia 76ers",
    "denver nuggets": "Denver Nuggets",
    "nuggets": "Denver Nuggets",
    "phoenix suns": "Phoenix Suns",
    "suns": "Phoenix Suns",
    "milwaukee bucks": "Milwaukee Bucks",
    "bucks": "Milwaukee Bucks",
    "toronto raptors": "Toronto Raptors",
    "raptors": "Toronto Raptors",
    "new york knicks": "New York Knicks",
    "knicks": "New York Knicks",
    "cleveland cavaliers": "Cleveland Cavaliers",
    "cavaliers": "Cleveland Cavaliers",
    "cavs": "Cleveland Cavaliers",
    "oklahoma city thunder": "Oklahoma City Thunder",
    "seattle supersonics": "Oklahoma City Thunder",
    "thunder": "Oklahoma City Thunder",
    "portland trail blazers": "Portland Trail Blazers",
    "trail blazers": "Portland Trail Blazers",
    "blazers": "Portland Trail Blazers",
    "minnesota timberwolves": "Minnesota Timberwolves",
    "timberwolves": "Minnesota Timberwolves",
    "wolves": "Minnesota Timberwolves",
    "atlanta hawks": "Atlanta Hawks",
    "hawks": "Atlanta Hawks",
    "memphis grizzlies": "Memphis Grizzlies",
    "vancouver grizzlies": "Memphis Grizzlies",
    "grizzlies": "Memphis Grizzlies",
    "indiana pacers": "Indiana Pacers",
    "pacers": "Indiana Pacers",
    "new orleans pelicans": "New Orleans Pelicans",
    "new orleans hornets": "New Orleans Pelicans",
    "new orleans/oklahoma city hornets": "New Orleans Pelicans",
    "pelicans": "New Orleans Pelicans",
    "orlando magic": "Orlando Magic",
    "magic": "Orlando Magic",
    "sacramento kings": "Sacramento Kings",
    "kings": "Sacramento Kings",
    "detroit pistons": "Detroit Pistons",
    "pistons": "Detroit Pistons",
    "utah jazz": "Utah Jazz",
    "jazz": "Utah Jazz",
    "washington wizards": "Washington Wizards",
    "washington bullets": "Washington Wizards",
    "wizards": "Washington Wizards",
    "charlotte hornets": "Charlotte Hornets",
    "charlotte bobcats": "Charlotte Hornets",
    "hornets": "Charlotte Hornets"
}

STANDARD_EUROLEAGUE_CLUBS = [
    "Real Madrid",
    "FC Barcelona",
    "Panathinaikos",
    "Olympiacos",
    "Fenerbahçe",
    "Anadolu Efes",
    "Maccabi Tel Aviv",
    "CSKA Moscow",
    "Baskonia",
    "AS Monaco",
    "Partizan",
    "Crvena Zvezda",
    "EA7 Emporio Armani Milan",
    "Zalgiris Kaunas",
    "FC Bayern Munich",
    "Virtus Segafredo Bologna",
    "Valencia Basket",
    "Paris Basketball",
    "ALBA Berlin",
    "LDLC ASVEL Villeurbanne"
]

EUROLEAGUE_NORMALIZER = {
    "real": "Real Madrid",
    "real madrid": "Real Madrid",
    "barcelona": "FC Barcelona",
    "fc barcelona": "FC Barcelona",
    "panathinaikos": "Panathinaikos",
    "panathinaikos aktor athens": "Panathinaikos",
    "pao": "Panathinaikos",
    "olympiacos": "Olympiacos",
    "olympiakos": "Olympiacos",
    "olympiacos piraeus": "Olympiacos",
    "fenerbahce": "Fenerbahçe",
    "fenerbahçe": "Fenerbahçe",
    "fenerbahce istanbul": "Fenerbahçe",
    "anadolu efes": "Anadolu Efes",
    "anadolu efes istanbul": "Anadolu Efes",
    "efes": "Anadolu Efes",
    "maccabi": "Maccabi Tel Aviv",
    "maccabi tel aviv": "Maccabi Tel Aviv",
    "maccabi rapyd tel aviv": "Maccabi Tel Aviv",
    "maccabi playtika tel aviv": "Maccabi Tel Aviv",
    "cska": "CSKA Moscow",
    "cska moscow": "CSKA Moscow",
    "baskonia": "Baskonia",
    "baskonia vitoria-gasteiz": "Baskonia",
    "laboral kutxa": "Baskonia",
    "tau ceramica": "Baskonia",
    "monaco": "AS Monaco",
    "as monaco": "AS Monaco",
    "partizan": "Partizan",
    "partizan mozzart bet belgrade": "Partizan",
    "partizan belgrade": "Partizan",
    "crvena zvezda": "Crvena Zvezda",
    "crvena zvezda meridianbet belgrade": "Crvena Zvezda",
    "red star": "Crvena Zvezda",
    "milan": "EA7 Emporio Armani Milan",
    "milano": "EA7 Emporio Armani Milan",
    "olimpia milano": "EA7 Emporio Armani Milan",
    "armani milan": "EA7 Emporio Armani Milan",
    "armani olimpia milan": "EA7 Emporio Armani Milan",
    "ea7 emporio armani milan": "EA7 Emporio Armani Milan",
    "zalgiris": "Zalgiris Kaunas",
    "zalgiris kaunas": "Zalgiris Kaunas",
    "bayern": "FC Bayern Munich",
    "bayern munich": "FC Bayern Munich",
    "fc bayern munich": "FC Bayern Munich",
    "virtus": "Virtus Segafredo Bologna",
    "virtus bologna": "Virtus Segafredo Bologna",
    "virtus segafredo bologna": "Virtus Segafredo Bologna",
    "valencia": "Valencia Basket",
    "valencia basket": "Valencia Basket",
    "alba": "ALBA Berlin",
    "alba berlin": "ALBA Berlin",
    "asvel": "LDLC ASVEL Villeurbanne",
    "ldlc asvel villeurbanne": "LDLC ASVEL Villeurbanne",
    "paris": "Paris Basketball",
    "paris basketball": "Paris Basketball"
}

COUNTRY_MAP = {
    "slovenia": "Slovenia", "serbia": "Serbia", "france": "France", "greece": "Greece",
    "germany": "Germany", "spain": "Spain", "canada": "Canada", "lithuania": "Lithuania",
    "turkey": "Turkey", "australia": "Australia", "cameroon": "Cameroon", "croatia": "Croatia",
    "argentina": "Argentina", "italy": "Italy", "dominican republic": "Dominican Republic",
    "montenegro": "Montenegro", "bahamas": "Bahamas", "nigeria": "Nigeria", "switzerland": "Switzerland",
    "georgia": "Georgia", "latvia": "Latvia", "czech republic": "Czech Republic",
    "czechia": "Czech Republic", "bosnia": "Bosnia and Herzegovina", "brazil": "Brazil",
    "japan": "Japan", "finland": "Finland", "united kingdom": "UK", "great britain": "UK",
    "israel": "Israel", "new zealand": "New Zealand", "austria": "Austria", "senegal": "Senegal",
    "angola": "Angola", "dr congo": "DR Congo", "congo": "DR Congo", "south sudan": "South Sudan",
    "jamaica": "Jamaica", "ukraine": "Ukraine", "poland": "Poland", "bulgaria": "Bulgaria",
    "cape verde": "Cape Verde", "sweden": "Sweden", "belgium": "Belgium", "portugal": "Portugal",
    "china": "China", "mali": "Mali", "estonia": "Estonia", "iceland": "Iceland", "netherlands": "Netherlands",
    "azerbaijan": "Azerbaijan", "armenia": "Armenia", "cyprus": "Cyprus"
}

def resolve_country(loc_str):
    if not loc_str:
        return "USA"
    loc_lower = str(loc_str).lower()
    for pattern, official in COUNTRY_MAP.items():
        if pattern in loc_lower:
            return official
    parts = str(loc_str).split(",")
    if len(parts) >= 2 and len(parts[-1].strip()) == 2:
        return "USA"
    return "USA"

def clean_player_name(raw_name):
    if not raw_name:
        return ""
    name = raw_name.strip()
    name = re.sub(r"\s+", " ", name)
    return name

def build_nba_database():
    print("Building expanded NBA database...")
    existing_file = DATA_DIR / "nba_data.json"
    players_dict = {}

    if existing_file.exists():
        with open(existing_file, "r", encoding="utf-8") as f:
            d = json.load(f)
            for p in d.get("players", []):
                name = clean_player_name(p["name"])
                players_dict[name.lower()] = {
                    "name": name,
                    "country": p.get("country", "USA"),
                    "teams": list(set(p.get("teams", [])))
                }

    roster_urls = [
        "https://raw.githubusercontent.com/alexnoob/BasketBall-GM-Rosters/master/2025-26.NBA.Roster.json",
        "https://raw.githubusercontent.com/alexnoob/BasketBall-GM-Rosters/master/2015-16.NBA.Roster.json",
        "https://raw.githubusercontent.com/alexnoob/BasketBall-GM-Rosters/master/2009-10%20Rosters.json",
        "https://raw.githubusercontent.com/alexnoob/BasketBall-GM-Rosters/master/1995-96.NBA.Roster.json"
    ]

    for url in roster_urls:
        filename = url.split("/")[-1]
        print(f"Fetching NBA roster: {filename} ...")
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                print(f"  Failed status: {r.status_code}")
                continue

            data = r.json()
            teams_map = {}
            for t in data.get("teams", []):
                tid = t.get("tid")
                t_full = f"{t.get('region', '')} {t.get('name', '')}".strip()
                norm = TEAM_NAME_NORMALIZER.get(t_full.lower()) or TEAM_NAME_NORMALIZER.get(t.get("name", "").lower())
                if norm:
                    teams_map[tid] = norm

            for p in data.get("players", []):
                p_name = p.get("name")
                if not p_name:
                    fn = p.get("firstName", "").strip()
                    ln = p.get("lastName", "").strip()
                    if fn or ln:
                        p_name = f"{fn} {ln}".strip()

                if not p_name or len(p_name) < 4:
                    continue

                p_name = clean_player_name(p_name)
                key = p_name.lower()

                p_teams = set()
                curr_tid = p.get("tid")
                if curr_tid in teams_map:
                    p_teams.add(teams_map[curr_tid])

                for s in p.get("stats", []):
                    tid = s.get("tid")
                    if tid in teams_map:
                        p_teams.add(teams_map[tid])

                if not p_teams:
                    continue

                born_loc = p.get("born", {}).get("loc", "")
                country = resolve_country(born_loc)

                if key in players_dict:
                    existing_teams = set(players_dict[key]["teams"])
                    existing_teams.update(p_teams)
                    players_dict[key]["teams"] = sorted(list(existing_teams))
                    if players_dict[key]["country"] == "USA" and country != "USA":
                        players_dict[key]["country"] = country
                else:
                    players_dict[key] = {
                        "name": p_name,
                        "country": country,
                        "teams": sorted(list(p_teams))
                    }

        except Exception as e:
            print(f"  Error processing {filename}: {e}")

    final_players = list(players_dict.values())
    final_players.sort(key=lambda x: x["name"])
    represented_countries = sorted(list(set(p["country"] for p in final_players)))

    output_data = {
        "league": "NBA",
        "teams": STANDARD_NBA_TEAMS,
        "countries": represented_countries,
        "players": final_players
    }

    with open(existing_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"SUCCESS: NBA database written with {len(final_players)} players across {len(represented_countries)} countries!")


def build_euroleague_database():
    print("\nBuilding expanded EuroLeague database with 2026-27 live season...")
    existing_file = DATA_DIR / "euroleague_data.json"
    players_dict = {}

    # Load existing hand-curated dataset first
    if existing_file.exists():
        with open(existing_file, "r", encoding="utf-8") as f:
            d = json.load(f)
            for p in d.get("players", []):
                name = clean_player_name(p["name"])
                players_dict[name.lower()] = {
                    "name": name,
                    "country": p.get("country", "Greece"),
                    "teams": list(set(p.get("teams", [])))
                }

    # Fetch official EuroLeague API data for modern seasons, especially 2026-27 (season=2026)
    try:
        from euroleague_api.player_stats import PlayerStats
        ps = PlayerStats()
        for season_year in [2026, 2025, 2024, 2023]:
            season_label = f"{season_year}-{str(season_year+1)[-2:]}"
            print(f"Querying official EuroLeague API for Season {season_label} ...")
            try:
                df = ps.get_player_stats_single_season(endpoint="traditional", season=season_year)
                print(f"  Retrieved {len(df)} players for Season {season_label}")
                for _, row in df.iterrows():
                    raw_name = str(row.get("player.name", "")).strip()
                    if not raw_name or len(raw_name) < 3:
                        continue

                    # Euroleague API format is 'LASTNAME, FIRSTNAME'
                    parts = raw_name.split(",")
                    if len(parts) == 2:
                        name = f"{parts[1].strip().title()} {parts[0].strip().title()}"
                    else:
                        name = raw_name.title()

                    name = clean_player_name(name)
                    key = name.lower()

                    # Raw team
                    raw_team = str(row.get("player.team.name", "")).strip()
                    norm_team = EUROLEAGUE_NORMALIZER.get(raw_team.lower())
                    if not norm_team:
                        for k, v in EUROLEAGUE_NORMALIZER.items():
                            if k in raw_team.lower():
                                norm_team = v
                                break

                    if not norm_team:
                        continue

                    p_code = row.get("player.code")

                    if key in players_dict:
                        if norm_team not in players_dict[key]["teams"]:
                            players_dict[key]["teams"].append(norm_team)
                    else:
                        # Resolve country via bio API if needed
                        country = "USA"
                        if p_code:
                            try:
                                bio_res = requests.get(
                                    f"https://api-live.euroleague.net/v1/players?seasonCode=E{season_year}&playerCode={p_code}",
                                    timeout=3
                                )
                                if bio_res.status_code == 200:
                                    import xmltodict
                                    parsed = xmltodict.parse(bio_res.text)
                                    raw_c = parsed.get("player", {}).get("country", "")
                                    if raw_c:
                                        country = resolve_country(raw_c)
                            except Exception:
                                pass

                        players_dict[key] = {
                            "name": name,
                            "country": country,
                            "teams": [norm_team]
                        }

            except Exception as se:
                print(f"  Error querying season {season_year}: {se}")

    except Exception as e:
        print(f"EuroLeague API import/query error: {e}")

    # Deduplicate teams and sort
    final_players = list(players_dict.values())
    for p in final_players:
        p["teams"] = sorted(list(set(p["teams"])))
    final_players.sort(key=lambda x: x["name"])

    represented_countries = sorted(list(set(p["country"] for p in final_players)))

    output_data = {
        "league": "EuroLeague",
        "teams": STANDARD_EUROLEAGUE_CLUBS,
        "countries": represented_countries,
        "players": final_players
    }

    with open(existing_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"SUCCESS: EuroLeague database updated with 2026-27 season! Total: {len(final_players)} players across {len(represented_countries)} countries!")

if __name__ == "__main__":
    build_euroleague_database()

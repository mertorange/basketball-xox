"""
Database Builder for Basketball XOX
Rebuilds the NBA and EuroLeague player datasets from public sources.

NBA
  - Basketball GM community roster snapshots (1995-96, 2009-10, 2015-16 onwards)
    give each player's name, birth year, birthplace and team.
  - FiveThirtyEight's player-season table (1977-2020) fills in full career team
    histories, matched on name + birth year.
  - Wikidata (CC0) adds players the snapshots miss (mostly retired before 1995),
    pre-1977 team stints and birth countries, matched on name + birth year.

EuroLeague
  - Official EuroLeague API season registrations (2000-01 to the current season)
    give every player's clubs, including mid-season moves, and birth country.

A player's country is their birth country in both leagues.

Players from the previous dataset that no source covers (hand-curated legends)
are carried over with their club names normalized.

Usage:
    python backend/scripts/build_databases.py [--league nba|euroleague|all] [--out DIR]

Only the Python standard library is needed.
"""

import argparse
import csv
import io
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
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

# Basketball-Reference team ids (used by FiveThirtyEight) -> current franchise.
# The 1988-2002 Charlotte Hornets history belongs to today's Charlotte franchise.
BREF_TEAM_TO_FRANCHISE = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BRK": "Brooklyn Nets", "NJN": "Brooklyn Nets", "NYN": "Brooklyn Nets",
    "BUF": "LA Clippers", "SDC": "LA Clippers", "LAC": "LA Clippers",
    "CHA": "Charlotte Hornets", "CHH": "Charlotte Hornets", "CHO": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "KCK": "Sacramento Kings", "SAC": "Sacramento Kings",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies", "VAN": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOH": "New Orleans Pelicans", "NOK": "New Orleans Pelicans", "NOP": "New Orleans Pelicans",
    "NOJ": "Utah Jazz", "UTA": "Utah Jazz",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "SEA": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "WAS": "Washington Wizards", "WSB": "Washington Wizards",
}

NBA_ROSTER_BASE = "https://raw.githubusercontent.com/alexnoob/BasketBall-GM-Rosters/master/"
NBA_ROSTER_FILES = ["1995-96.NBA.Roster.json", "2009-10 Rosters.json"] + [
    f"{y}-{str(y + 1)[-2:]}.NBA.Roster.json" for y in range(2015, 2026)
]
# Birth years in this file are shifted by about nine years and most birthplaces are
# college names, so births come from FiveThirtyEight and countries from fallbacks.
NBA_ROSTERS_WITH_BAD_BIOS = {"2009-10 Rosters.json"}
# Birth countries set by hand; they win over every source. Mostly players whose only
# roster entry is in that file: either no birthplace at all (straight-from-high-school
# or international signings) or an American college that would otherwise make them USA.
NBA_COUNTRY_OVERRIDES = {
    "Al Harrington": "USA", "Andray Blatche": "USA", "Andrew Bynum": "USA", "Andris Biedrins": "Latvia",
    "Darko Milicic": "Serbia", "DeSagana Diop": "Senegal", "DeShawn Stevenson": "USA", "Eddy Curry": "USA",
    "Hamed Haddadi": "Iran", "Jermaine O'Neal": "USA", "Kwame Brown": "USA", "Nene Hilario": "Brazil",
    "Rashard Lewis": "USA", "Sebastian Telfair": "USA", "Tracy McGrady": "USA", "Yi Jianlian": "China",
    "Zydrunas Ilgauskas": "Lithuania",
    "Eduardo Najera": "Mexico", "Francisco Garcia": "Dominican Republic", "Hasheem Thabeet": "Tanzania",
    "Jamaal Magloire": "Canada", "Kelenna Azubuike": "UK", "Nathan Jawai": "Australia", "Ronny Turiaf": "France",
    "Samuel Dalembert": "Haiti",
    # Roster lists where they grew up; Wikidata has the birthplace
    "Ben Gordon": "UK", "Carlos Boozer": "Germany",
    # Wikidata links the wrong Horsham (Australia, not Pennsylvania)
    "Matt Carroll": "USA",
}
FIVETHIRTYEIGHT_URL = (
    "https://raw.githubusercontent.com/fivethirtyeight/nba-player-advanced-metrics/master/nba-data-historical.csv"
)

# Current-season rosters (the community snapshots lag a season behind: summer signings
# such as Marcus Smart to Houston in July 2026 are missing from them)
ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
# Wikidata team items -> current franchise (current teams plus former names with their own item)
WIKIDATA_NBA_TEAMS = {
    "Q131364": "New York Knicks", "Q131371": "Boston Celtics", "Q159893": "Atlanta Hawks",
    "Q169661": "Detroit Pistons", "Q138089": "Philadelphia 76ers", "Q157376": "Golden State Warriors",
    "Q121783": "Los Angeles Lakers", "Q976396": "LA Clippers", "Q169637": "Milwaukee Bucks",
    "Q164177": "Phoenix Suns", "Q572134": "Brooklyn Nets", "Q162954": "Denver Nuggets",
    "Q128109": "Chicago Bulls", "Q161345": "Houston Rockets", "Q159729": "San Antonio Spurs",
    "Q167253": "Portland Trail Blazers", "Q170329": "Indiana Pacers", "Q166105": "Sacramento Kings",
    "Q132893": "Dallas Mavericks", "Q162990": "Cleveland Cavaliers", "Q169165": "Washington Wizards",
    "Q169138": "Miami Heat", "Q161337": "Orlando Magic", "Q163480": "Charlotte Hornets",
    "Q170558": "Minnesota Timberwolves", "Q170649": "Utah Jazz", "Q172339": "New Orleans Pelicans",
    "Q132880": "Toronto Raptors", "Q165529": "Memphis Grizzlies", "Q180950": "Oklahoma City Thunder",
    "Q235326": "Oklahoma City Thunder",   # Seattle SuperSonics
    "Q3307390": "Memphis Grizzlies",      # Vancouver Grizzlies
    "Q18691677": "Golden State Warriors", # Philadelphia Warriors
    "Q12870869": "Sacramento Kings",      # Cincinnati Royals
    "Q5397091": "Philadelphia 76ers",     # Syracuse Nationals
    "Q1100222": "LA Clippers",            # Buffalo Braves
    "Q29996625": "LA Clippers",           # San Diego Clippers
    "Q4852796": "Washington Wizards",     # Baltimore Bullets (1963-73)
    "Q2928103": "Washington Wizards",     # Washington Bullets
    "Q115657357": "Brooklyn Nets",        # New Jersey Nets
    "Q6020894": "Atlanta Hawks",          # St. Louis Hawks
}
# Undated memberships mix in coaching jobs (Phil Jackson 'joins' the Bulls), and the
# Pelicans item also carries some 1988-2002 Charlotte Hornets stints, so Wikidata teams
# are only trusted for the years before FiveThirtyEight's coverage starts.
FIVETHIRTYEIGHT_FIRST_SEASON = 1977
BASKETBALL_COACH = "Q5137571"
US_TERRITORIES = {"Puerto Rico", "U.S. Virgin Islands", "Guam"}
WIKIDATA_QUERY = """
SELECT ?p ?pLabel ?dob ?team ?start ?countryLabel ?coach WHERE {
  VALUES ?team { %s }
  ?p p:P54 ?st . ?st ps:P54 ?team .
  ?p wdt:P31 wd:Q5 .
  OPTIONAL { ?st pq:P580 ?start }
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
    "LDLC ASVEL Villeurbanne",
    "Beşiktaş",
    "Dubai Basketball",
    "Hapoel Tel Aviv"
]

# Exact (lowercased) club names seen in the EuroLeague API since 2000 -> canonical club.
# Matching is exact on purpose: "Ulker" (Ülkerspor) is not "Fenerbahce Ulker", and
# "Skipper Bologna" (Fortitudo) is not Virtus.
EUROLEAGUE_CLUB_ALIASES = {
    "Real Madrid": ["real", "real madrid"],
    "FC Barcelona": ["barcelona", "fc barcelona", "fc barcelona lassa", "fc barcelona regal", "axa fc barcelona",
                     "regal barcelona", "regal fc barcelona", "winterthur fc barcelona"],
    "Panathinaikos": ["panathinaikos", "pao", "panathinaikos athens", "panathinaikos aktor athens",
                      "panathinaikos opap athens", "panathinaikos superfoods athens"],
    "Olympiacos": ["olympiacos", "olympiakos", "olympiacos piraeus"],
    "Fenerbahçe": ["fenerbahce", "fenerbahçe", "fenerbahce istanbul", "fenerbahce beko istanbul",
                   "fenerbahce dogus istanbul", "fenerbahce tarfin istanbul", "fenerbahce ulker",
                   "fenerbahce ulker istanbul"],
    "Anadolu Efes": ["efes", "anadolu efes", "anadolu efes istanbul", "efes pilsen", "efes pilsen istanbul"],
    "Maccabi Tel Aviv": ["maccabi", "maccabi tel aviv", "maccabi electra", "maccabi electra tel aviv", "maccabi elite",
                         "maccabi elite tel aviv", "maccabi fox tel aviv", "maccabi playtika tel aviv",
                         "maccabi rapyd tel aviv"],
    "CSKA Moscow": ["cska", "cska moscow"],
    "Baskonia": ["baskonia", "baskonia vitoria gasteiz", "baskonia vitoria-gasteiz", "bitci baskonia vitoria-gasteiz",
                 "caja laboral", "caja laboral vitoria", "cazoo baskonia vitoria-gasteiz",
                 "kirolbet baskonia vitoria gasteiz", "kirolbet baskonia vitoria-gasteiz",
                 "kosner baskonia vitoria-gasteiz", "laboral kutxa", "laboral kutxa vitoria",
                 "laboral kutxa vitoria gasteiz", "tau ceramica", "tau ceramica vitoria-gasteiz",
                 "td systems baskonia vitoria-gasteiz"],
    "AS Monaco": ["monaco", "as monaco"],
    "Partizan": ["partizan", "partizan belgrade", "partizan igokea", "partizan mozzart bet belgrade",
                 "partizan nis belgrade", "partizan mt:s belgrade"],
    "Crvena Zvezda": ["crvena zvezda", "red star", "crvena zvezda meridianbet belgrade",
                      "crvena zvezda telekom belgrade", "crvena zvezda mts belgrade"],
    "EA7 Emporio Armani Milan": ["milan", "milano", "olimpia milano", "aj milano", "armani jeans milano", "armani milan",
                                 "armani olimpia milan", "ax armani exchange milan",
                                 "ax armani exchange olimpia milan", "ea7 emporio armani",
                                 "ea7 emporio armani milan"],
    "Zalgiris Kaunas": ["zalgiris", "zalgiris kaunas"],
    "FC Bayern Munich": ["bayern", "bayern munich", "fc bayern munich"],
    "Virtus Segafredo Bologna": ["virtus", "virtus bologna", "virtus segafredo bologna", "kinder virtus bologna",
                                 "virtus vidivici"],
    "Valencia Basket": ["valencia", "valencia basket", "pamesa valencia", "power electronics valencia"],
    "Paris Basketball": ["paris", "paris basketball"],
    "ALBA Berlin": ["alba", "alba berlin"],
    "LDLC ASVEL Villeurbanne": ["asvel", "asvel basket", "ldlc asvel villeurbanne"],
    "Beşiktaş": ["besiktas", "besiktas istanbul", "besiktas jk istanbul"],
    "Dubai Basketball": ["dubai basketball"],
    "Hapoel Tel Aviv": ["hapoel ibi tel aviv"],
    # Former EuroLeague clubs (kept on player profiles, not used as grid criteria)
    "Unicaja": ["unicaja", "unicaja malaga"],
    "Darüşşafaka": ["darussafaka", "darussafaka dogus istanbul", "darussafaka tekfen istanbul"],
    "Khimki": ["khimki", "khimki moscow region", "bc khimki moscow region"],
    "Brose Bamberg": ["brose bamberg", "brose baskets", "brose baskets bamberg", "ghp bamberg"],
    "Cibona": ["cibona", "cibona vip", "cibona zagreb"],
    "Union Olimpija": ["union olimpija", "union olimpija ljubljana"],
    "Galatasaray": ["galatasaray liv hospital istanbul", "galatasaray medical park", "galatasaray odeabank istanbul"],
    "Lietuvos Rytas": ["lietuvos rytas", "lietuvos rytas vilnius"],
    "Prokom Gdynia": ["asseco prokom", "asseco prokom gdynia", "prokom trefl sopot"],
    "UNICS Kazan": ["unics kazan"],
    "Benetton Treviso": ["benetton basket", "benetton treviso"],
    "Fortitudo Bologna": ["climamio bologna", "skipper bologna", "skipper fortitudo bologna"],
    "Buducnost": ["buducnost", "kk buducnost", "buducnost voli pogdorica"],
    "Spirou Charleroi": ["spirou basket", "spirou charleroi", "belgacom spirou charleroi",
                         "region wallone spirou charleroi"],
    "Cantu": ["bennet cantu", "mapooro cantu"],
    "London Towers": ["haribo london towers", "kinder london towers"],
}
EUROLEAGUE_CLUB_NORMALIZER = {
    alias: club for club, aliases in EUROLEAGUE_CLUB_ALIASES.items() for alias in aliases
}

# The API returns 500 records unless asked for more (2001-02 has 527 registrations)
EUROLEAGUE_PEOPLE_URL = (
    "https://api-live.euroleague.net/v2/competitions/E/seasons/E{season}/people?personType=J&limit=2000"
)
EUROLEAGUE_FIRST_SEASON = 2000

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "IO",  # roster typo for Iowa
}

# "Georgia" is left out: after a comma the rosters use state codes, so "Tbilisi, Georgia" is the country.
US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio", "oklahoma",
    "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah",
    "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming",
}

COUNTRY_ALIASES = {
    "united states of america": "USA", "united states": "USA", "usa": "USA",
    "england": "UK", "scotland": "UK", "wales": "UK", "united kingdom": "UK", "great britain": "UK",
    "italia": "Italy",
    "russian federation": "Russia",
    "turkiye": "Turkey", "türkiye": "Turkey",
    "bosnia": "Bosnia and Herzegovina", "bosnia & herzegovina": "Bosnia and Herzegovina",
    "republic of bosnia and herzegovina": "Bosnia and Herzegovina",
    "democratic republic of the congo": "DR Congo", "democratic republic of the congo (zaire)": "DR Congo",
    "dr congo": "DR Congo", "congo": "Republic of the Congo",
    "macedonia": "North Macedonia",
    "french guyana": "France",
    "czechia": "Czech Republic",
    "cabo verde": "Cape Verde",
    "cote d’ivoire": "Ivory Coast", "cote d'ivoire": "Ivory Coast",
    "the bahamas": "Bahamas", "people's republic of china": "China", "kingdom of the netherlands": "Netherlands",
    "united states virgin islands": "U.S. Virgin Islands", "republic of ireland": "Ireland",
    "the gambia": "Gambia", "democratic republic of congo": "DR Congo",
    "no country": None,
}

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def http_get(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "basketball-xox-builder"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except (urllib.error.URLError, TimeoutError) as e:
            err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {err}")


def parse_json_lenient(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some community roster files carry trailing commas
        return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def ascii_fold(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def clean_player_name(raw_name):
    if not raw_name:
        return ""
    name = ascii_fold(raw_name.strip())
    name = re.sub(r"\s+", " ", name)
    return name


def name_key(name):
    """Comparison key: 'R.J. Barrett', 'RJ Barrett' and 'R. J. Barrett' share one."""
    key = ascii_fold(name).lower()
    key = re.sub(r"[.'’`]", "", key)
    key = re.sub(r"[-\s]+", " ", key).strip()
    # Join spaced initials: 'a c green' -> 'ac green'
    return re.sub(r"\b([a-z]) (?=[a-z]\b)", r"\1", key)


def base_name_key(name):
    """name_key without Jr./Sr./II/III suffixes: 'Kelly Oubre Jr.' -> 'kelly oubre'."""
    parts = name_key(name).split()
    while len(parts) > 1 and parts[-1] in NAME_SUFFIXES:
        parts.pop()
    return " ".join(parts)


def canonical_country(name):
    if not name:
        return None
    name = name.strip()
    lowered = name.lower()
    if lowered in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[lowered]
    return name


def resolve_birthplace(loc):
    """Returns the birth country for a Basketball GM 'born.loc' value, or None.

    Country means birthplace in both leagues. Newer rosters append a national team
    ('Tampa, FL - Country: Philippines'); it is used only when the birthplace itself is
    unusable. Bare values without a comma are college or state names from older rosters
    and carry no country.
    """
    if not loc:
        return None
    loc = loc.strip()
    m = re.search(r"\s-\s*Country:\s*(.+)$", loc)
    if m:
        return resolve_birthplace(loc[:m.start()]) or canonical_country(m.group(1))
    if "," not in loc:
        return None
    city, region = (part.strip() for part in loc.rsplit(",", 1))
    if region.upper() in US_STATE_CODES or region.lower() in US_STATE_NAMES:
        return "USA"
    if region.lower() == "congo" and city.lower() == "kinshasa":
        return "DR Congo"
    return canonical_country(region)


def format_euroleague_name(raw_name):
    """'MCCORMACK, DAVID' -> 'David McCormack'."""
    parts = raw_name.split(",", 1)
    name = f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else raw_name
    name = clean_player_name(name).title()
    name = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), name)
    name = re.sub(r"\b(Ii|Iii|Iv)\b", lambda m: m.group(1).upper(), name)
    return re.sub(r"\bJr\b\.?", "Jr.", name)


def normalize_euroleague_club(raw_club):
    raw_club = (raw_club or "").strip()
    return EUROLEAGUE_CLUB_NORMALIZER.get(raw_club.lower(), raw_club)


def load_previous_players(filename):
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("players", [])


def write_dataset(out_dir, filename, league, teams, players):
    players.sort(key=lambda p: p["name"])
    countries = sorted({p["country"] for p in players if p["country"]})
    out_path = out_dir / filename
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"league": league, "teams": teams, "countries": countries, "players": players},
                  f, indent=2, ensure_ascii=False)
    print(f"SUCCESS: {out_path} written with {len(players)} players across {len(countries)} countries.")


def load_fivethirtyeight():
    """Returns (career, season_births) from FiveThirtyEight's player-season table.

    career: (base name, possible birth year) -> {player_id: franchises}
    season_births: (base name, season) -> {player_id: birth year}
    """
    print("Fetching FiveThirtyEight player-season history ...")
    career = defaultdict(lambda: defaultdict(set))
    season_births = defaultdict(dict)
    for row in csv.DictReader(io.StringIO(http_get(FIVETHIRTYEIGHT_URL))):
        team = BREF_TEAM_TO_FRANCHISE.get(row["team_id"])
        if not team or not row["age"].isdigit():
            continue
        base = base_name_key(row["name_common"])
        # Ages are taken on Feb 1 of the season, so the birth year is one of two
        birth_year = int(row["year_id"]) - int(row["age"])
        for year in (birth_year - 1, birth_year):
            career[(base, year)][row["player_id"]].add(team)
        season_births[(base, int(row["year_id"]))][row["player_id"]] = birth_year - 1
    return career, season_births


def load_espn_rosters():
    """Current NBA rosters from ESPN as (season, name, birth year, birthplace, team) rows."""
    print("Fetching current NBA rosters from ESPN ...")
    teams = json.loads(http_get(ESPN_TEAMS_URL))["sports"][0]["leagues"][0]["teams"]
    rows = []
    for item in teams:
        team = TEAM_NAME_NORMALIZER.get(item["team"]["displayName"].lower())
        if not team:
            print(f"  Unknown ESPN team {item['team']['displayName']!r}, skipped")
            continue
        roster = json.loads(http_get(ESPN_ROSTER_URL.format(team_id=item["team"]["id"])))
        season = (roster.get("season") or {}).get("year")
        for athlete in roster.get("athletes", []):
            born = athlete.get("dateOfBirth", "")[:4]
            place = athlete.get("birthPlace") or {}
            # Same shape as the roster snapshots: 'City, ST' for Americans, 'City, Country' otherwise
            region = place.get("state") if place.get("country") == "USA" and place.get("state") else place.get("country")
            loc = f"{place.get('city', '')}, {region}" if region else ""
            rows.append((season, clean_player_name(athlete.get("fullName", "")),
                         int(born) if born.isdigit() else None, loc, team))
    print(f"  {len(rows)} players on {len(teams)} rosters")
    return rows


def load_wikidata_players():
    """NBA franchise members from Wikidata with birth year, birth country and team stints."""
    print("Querying Wikidata for NBA players ...")
    url = WIKIDATA_SPARQL_URL + "?" + urllib.parse.urlencode({"query": WIKIDATA_QUERY, "format": "json"})
    rows = json.loads(http_get(url))["results"]["bindings"]
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
        if start.isdigit():
            if team == "New Orleans Pelicans" and int(start) < 2002:
                team = "Charlotte Hornets"
            entry["dated"].add((int(start), team))
        else:
            entry["undated"].add(team)
        if "countryLabel" in row:
            entry["countries"].add(canonical_country(row["countryLabel"]["value"]))
    for entry in players.values():
        # A few birthplaces list several current countries (or a US state); USA wins ties
        countries = entry.pop("countries")
        entry["country"] = "USA" if "USA" in countries else (min(countries) if countries else None)
    print(f"  {len(players)} players")
    return players


def wikidata_teams(entry, before=None, include_undated=True):
    """Franchises from Wikidata stints; undated stints count only for non-coaches."""
    teams = {team for start, team in entry["dated"] if before is None or start < before}
    if include_undated and not entry["coach"]:
        undated = set(entry["undated"])
        if "New Orleans Pelicans" in undated and (entry["born"] or 0) < 1975:
            undated.discard("New Orleans Pelicans")
            # Born before 1965: retired before the 2002 move, so a Charlotte-era stint
            if entry["born"] and entry["born"] < 1965:
                undated.add("Charlotte Hornets")
        teams |= undated
    return teams


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

    for season in range(EUROLEAGUE_FIRST_SEASON, date.today().year + 1):
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
                people[key] = {"names": [], "clubs": set(), "countries": [],
                               "born": int(birth_date[:4]) if birth_date else None}
                keys_by_name[key[0]].append(key)
            entry = people[key]
            entry["names"].append((season, name))
            entry["clubs"].add(club)
            # Birth country first: the registered nationality is often a second passport
            # (Ginobili and Scola are listed as Italian and Spanish)
            country = (canonical_country((person.get("birthCountry") or {}).get("name"))
                       or canonical_country((person.get("country") or {}).get("name")))
            if country:
                entry["countries"].append((season, country))

    _euroleague_people = people
    return people


def merge_roster_duplicates(people):
    """Merges roster entries that describe the same player.

    Snapshots disagree on details: birth years drift by up to two years, suffixes come
    and go ('Kelly Oubre' / 'Kelly Oubre Jr.'), surnames grow ('Timothe Luwawu' /
    'Timothe Luwawu-Cabarrot') and first names shorten ('Svi' / 'Sviatoslav'). Entries
    without a usable birth year join the only same-named player, if there is one.
    """
    dated = [(key[0], p) for key, p in people.items() if p["born"] is not None]
    undated = [(key[0], p) for key, p in people.items() if p["born"] is None]

    parent = list(range(len(dated)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_base = defaultdict(list)
    for i, (key, _) in enumerate(dated):
        by_base[base_name_key(key)].append(i)
    by_first_two = defaultdict(list)
    by_surname = defaultdict(list)
    for i, (key, _) in enumerate(dated):
        by_first_two[" ".join(key.split()[:2])].append(i)
        by_surname[" ".join(base_name_key(key).split()[1:])].append(i)

    def same_player(i, j):
        (key_i, a), (key_j, b) = dated[i], dated[j]
        gap = abs(a["born"] - b["born"])
        shared_team = bool(a["teams"] & b["teams"])
        if key_i == key_j:
            return gap <= 2
        base_i, base_j = base_name_key(key_i), base_name_key(key_j)
        if base_i == base_j:
            return gap <= 1
        words_i, words_j = key_i.split(), key_j.split()
        shorter, longer = sorted((words_i, words_j), key=len)
        if len(shorter) >= 2 and longer[:len(shorter)] == shorter:
            return gap <= 2 and shared_team
        # Short first names: 'Svi Mykhailiuk' / 'Sviatoslav Mykhailiuk', 'Ron Holland II' / 'Ronald Holland II'
        first_i, *rest_i = base_i.split()
        first_j, *rest_j = base_j.split()
        short, full = sorted((first_i, first_j), key=len)
        return rest_i == rest_j and len(short) >= 2 and full.startswith(short) and gap <= 1 and shared_team

    for group in list(by_base.values()) + list(by_first_two.values()) + list(by_surname.values()):
        for x in range(len(group)):
            for y in range(x + 1, len(group)):
                if same_player(group[x], group[y]):
                    parent[find(group[x])] = find(group[y])

    merged = {}
    for i, (_, person) in enumerate(dated):
        root = find(i)
        if root not in merged:
            merged[root] = {"names": [], "teams": set(), "countries": [], "born": person["born"],
                            "college_only": False}
        target = merged[root]
        target["names"] += person["names"]
        target["teams"] |= person["teams"]
        target["countries"] += person["countries"]
        target["college_only"] |= person["college_only"]
        # Keep the birth year from the most recent snapshot
        if max(person["names"]) >= max(target["names"]):
            target["born"] = person["born"]

    result = list(merged.values())
    for key, person in undated:
        same = [p for p in result if key in {name_key(n) for _, n in p["names"]}]
        if len(same) == 1:
            same[0]["names"] += person["names"]
            same[0]["teams"] |= person["teams"]
            same[0]["countries"] += person["countries"]
            same[0]["college_only"] |= person["college_only"]
        else:
            result.append(person)
    return result


def build_nba_database(out_dir):
    print("Building NBA database...")
    career, season_births = load_fivethirtyeight()
    # (name_key, birth_year) -> collected facts across roster snapshots
    people = {}

    for filename in NBA_ROSTER_FILES:
        print(f"Fetching NBA roster: {filename} ...")
        text = http_get(NBA_ROSTER_BASE + urllib.parse.quote(filename))
        if text is None:
            print("  Not found, skipped")
            continue
        data = parse_json_lenient(text)
        season = data.get("startingSeason") or int(filename[:4]) + 1

        teams_map = {}
        for t in data.get("teams", []):
            t_full = f"{t.get('region', '')} {t.get('name', '')}".strip()
            norm = TEAM_NAME_NORMALIZER.get(t_full.lower()) or TEAM_NAME_NORMALIZER.get(t.get("name", "").lower())
            if norm:
                teams_map[t.get("tid")] = norm

        for p in data.get("players", []):
            # Current team plus every team in the stats history (2019-20 onwards carry it,
            # including mid-season trades and free agents' past teams)
            teams = {teams_map[tid] for tid in [p.get("tid")] + [s.get("tid") for s in p.get("stats", [])]
                     if tid in teams_map}
            if not teams:  # draft prospects and players without NBA games
                continue
            raw_name = p.get("name") or f"{p.get('firstName', '')} {p.get('lastName', '')}"
            name = clean_player_name(raw_name)
            if len(name) < 3:
                continue
            born = p.get("born") or {}
            loc = (born.get("loc") or "").strip()
            if filename in NBA_ROSTERS_WITH_BAD_BIOS:
                births = season_births.get((base_name_key(name), season), {})
                birth_year = next(iter(births.values())) if len(births) == 1 else None
            else:
                birth_year = born.get("year")

            key = (name_key(name), birth_year)
            person = people.setdefault(key, {"names": [], "teams": set(), "countries": [], "born": birth_year,
                                             "college_only": False})
            person["names"].append((season, name))
            person["teams"] |= teams
            country = resolve_birthplace(loc)
            if country:
                person["countries"].append((season, country))
            elif loc:
                person["college_only"] = True

    for _season, name, birth_year, loc, team in load_espn_rosters():
        if len(name) < 3 or not birth_year:
            continue
        person = people.setdefault((name_key(name), birth_year), {
            "names": [], "teams": set(), "countries": [], "born": birth_year, "college_only": False})
        # Season 0: the display name stays the familiar roster spelling ('Ron Holland II',
        # not ESPN's 'Ronald Holland II'); ESPN names only show for brand-new players
        person["names"].append((0, name))
        person["teams"].add(team)
        country = resolve_birthplace(loc)
        if country:
            # Lowest priority: ESPN sometimes lists the national team as the birth country
            # (Sandro Mamukelashvili, born in New York, shows up as Georgia)
            person["countries"].append((0, country))

    people = merge_roster_duplicates(people)

    enriched = 0
    for person in people:
        base = base_name_key(max(person["names"])[1])
        candidates = career.get((base, person["born"]), {}) if person["born"] else {}
        if len(candidates) == 1:
            teams = next(iter(candidates.values()))
            if not teams <= person["teams"]:
                enriched += 1
            person["teams"] |= teams
    print(f"  Career history added teams for {enriched} players")

    # Wikidata, matched on name + birth year: birth country, and stints from before
    # FiveThirtyEight's coverage (a 1970s Buck who finished his career in the 1980s)
    wikidata = load_wikidata_players()
    wikidata_index = defaultdict(list)
    for qid, entry in wikidata.items():
        if entry["born"]:
            for year in (entry["born"] - 1, entry["born"], entry["born"] + 1):
                wikidata_index[(base_name_key(entry["name"]), year)].append(qid)
    matched_qids = set()
    for person in people:
        if not person["born"]:
            continue
        qids = {qid for _, spelling in person["names"]
                for qid in wikidata_index.get((base_name_key(spelling), person["born"]), [])}
        if len(qids) != 1:
            continue
        qid = qids.pop()
        entry = wikidata[qid]
        matched_qids.add(qid)
        person["wikidata_country"] = entry["country"]
        person["teams"] |= wikidata_teams(entry, before=FIVETHIRTYEIGHT_FIRST_SEASON, include_undated=False)
    print(f"  Wikidata matched {len(matched_qids)} roster players")

    # Country fallbacks for players whose only roster entry has no birthplace:
    # EuroLeague birth country, then a non-default country from the previous dataset,
    # then USA when the roster lists an American college instead of a birthplace.
    euroleague_country = {}
    for entry in fetch_euroleague_people().values():
        if entry["born"] and entry["countries"]:
            for year in (entry["born"] - 1, entry["born"], entry["born"] + 1):
                euroleague_country[(base_name_key(max(entry["names"])[1]), year)] = max(entry["countries"])[1]
    previous_country = {name_key(p["name"]): p.get("country") for p in load_previous_players("nba_data.json")}

    players = []
    country_sources = defaultdict(int)
    conflicts = []
    for person in people:
        name = max(person["names"])[1]  # latest spelling
        country = max(person["countries"])[1] if person["countries"] else None  # newest snapshot wins
        source = "roster"
        # Wikidata settles foreign birthplaces (Pekovic: Montenegro, not Serbia) and fills
        # gaps, but some of its American-born players point at a same-named foreign town
        # (Kendall Gill in Paisley, Scotland), and it files Puerto Rico under the USA.
        # A roster USA against a Wikidata foreign country is left alone; known cases of
        # that conflict are in NBA_COUNTRY_OVERRIDES.
        wikidata_country = person.get("wikidata_country")
        if wikidata_country and wikidata_country != country:
            if country == "USA" or (wikidata_country == "USA" and country in US_TERRITORIES):
                conflicts.append(f"{name} (roster {country}, Wikidata {wikidata_country})")
            else:
                country, source = wikidata_country, "wikidata" if not country else "wikidata correction"
        if name in NBA_COUNTRY_OVERRIDES:
            country, source = NBA_COUNTRY_OVERRIDES[name], "override"
        elif not country:
            if (base_name_key(name), person["born"]) in euroleague_country:
                country, source = euroleague_country[(base_name_key(name), person["born"])], "euroleague"
            elif previous_country.get(name_key(name)) not in (None, "", "USA", "Georgia"):
                country, source = previous_country[name_key(name)], "previous dataset"
            elif person["college_only"]:
                country, source = "USA", "US college"
            else:
                country, source = "", "unknown"
        country_sources[source] += 1
        players.append({"name": name, "country": country, "teams": sorted(person["teams"])})
    print(f"  Country sources: {dict(country_sources)}")
    if conflicts:
        print(f"  Kept roster country over Wikidata for {len(conflicts)}: {', '.join(conflicts)}")

    # Players no roster snapshot covers (retired before 1995 or between snapshots), from
    # Wikidata. FiveThirtyEight supplies their 1977+ teams when it knows them.
    roster_keys = {(base_name_key(spelling), year)
                   for p in people if p["born"] for _, spelling in p["names"]
                   for year in (p["born"] - 1, p["born"], p["born"] + 1)}
    roster_names = {name_key(p["name"]) for p in players}
    added = 0
    for qid, entry in wikidata.items():
        if qid in matched_qids or not entry["born"]:
            continue
        base = base_name_key(entry["name"])
        if (base, entry["born"]) in roster_keys or name_key(entry["name"]) in roster_names:
            continue
        stints = career.get((base, entry["born"]), {})
        if len(stints) == 1:
            teams = next(iter(stints.values())) | wikidata_teams(
                entry, before=FIVETHIRTYEIGHT_FIRST_SEASON, include_undated=entry["born"] < 1957)
        else:
            teams = wikidata_teams(entry)
        if not teams:
            continue
        players.append({"name": entry["name"], "country": entry["country"] or "", "teams": sorted(teams)})
        roster_names.add(name_key(entry["name"]))
        added += 1
    print(f"  {added} players added from Wikidata")

    # Carry over previous entries (hand-curated legends) that no roster snapshot covers.
    # A suffix variant only counts as covered when its teams fit: 'Tim Hardaway' is not
    # 'Tim Hardaway Jr.'.
    career_by_base = defaultdict(lambda: defaultdict(set))
    for (base, _), by_id in career.items():
        for pid, teams in by_id.items():
            career_by_base[base][pid] |= teams
    # Every spelling a roster used counts ('Sviatoslav Mykhailiuk' is now 'Svi Mykhailiuk')
    exact = {name_key(p["name"]) for p in players} | {name_key(s) for p in people for _, s in p["names"]}
    by_base = defaultdict(list)
    for p in players:
        by_base[base_name_key(p["name"])].append(set(p["teams"]))
    for p in people:
        for _, spelling in p["names"]:
            by_base[base_name_key(spelling)].append(p["teams"])
    carried = []
    for old in load_previous_players("nba_data.json"):
        teams = {t for t in old.get("teams", []) if t in STANDARD_NBA_TEAMS}
        base = base_name_key(old["name"])
        if name_key(old["name"]) in exact or any(teams <= t for t in by_base[base]):
            continue
        if len(career_by_base[base]) == 1:
            teams |= next(iter(career_by_base[base].values()))
        if teams:
            carried.append({"name": clean_player_name(old["name"]), "country": old.get("country", ""),
                            "teams": sorted(teams)})
            exact.add(name_key(old["name"]))
            by_base[base].append(teams)
    players += carried
    print(f"  {len(carried)} players carried over from the previous dataset")

    write_dataset(out_dir, "nba_data.json", "NBA", STANDARD_NBA_TEAMS, players)


def build_euroleague_database(out_dir):
    print("\nBuilding EuroLeague database...")
    criteria = set(STANDARD_EUROLEAGUE_CLUBS)
    players = []
    for entry in fetch_euroleague_people().values():
        if not entry["clubs"] & criteria:
            continue
        players.append({
            "name": max(entry["names"])[1],
            "country": max(entry["countries"])[1] if entry["countries"] else "",
            "teams": sorted(entry["clubs"]),
        })

    # Carry over previous entries (hand-curated legends from before 2000-01)
    by_key = {name_key(p["name"]): p for p in players}
    carried = 0
    for old in load_previous_players("euroleague_data.json"):
        clubs = {normalize_euroleague_club(t) for t in old.get("teams", [])}
        current = by_key.get(name_key(old["name"]))
        if current:
            # Pre-2000 stints only exist in the curated data
            current["teams"] = sorted(set(current["teams"]) | clubs)
            if not current["country"]:
                current["country"] = old.get("country", "")
            continue
        if clubs & criteria:
            carried += 1
            entry = {"name": clean_player_name(old["name"]), "country": old.get("country", ""),
                     "teams": sorted(clubs)}
            players.append(entry)
            by_key[name_key(entry["name"])] = entry
    print(f"  {carried} players carried over from the previous dataset")

    write_dataset(out_dir, "euroleague_data.json", "EuroLeague", STANDARD_EUROLEAGUE_CLUBS, players)


def main():
    parser = argparse.ArgumentParser(description="Rebuild Basketball XOX player datasets.")
    parser.add_argument("--league", choices=["nba", "euroleague", "all"], default="all")
    parser.add_argument("--out", type=Path, default=DATA_DIR,
                        help="output directory (default: backend/data, overwriting the current datasets)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.league in ("nba", "all"):
        build_nba_database(args.out)
    if args.league in ("euroleague", "all"):
        build_euroleague_database(args.out)


if __name__ == "__main__":
    sys.exit(main())

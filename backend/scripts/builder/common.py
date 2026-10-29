"""Shared helpers: HTTP, name keys, countries, dataset I/O."""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

# The live datasets; in Docker HOOPGRID_DATA_DIR points at the current release on the data volume
DATA_DIR = Path(os.environ.get("HOOPGRID_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")

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

# Letters NFKD does not split into a base letter plus accent
NON_DECOMPOSING = str.maketrans({"Đ": "D", "đ": "d", "Ø": "O", "ø": "o", "Ł": "L", "ł": "l", "ß": "ss",
                                 "Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe", "Þ": "Th", "þ": "th", "ı": "i"})


def ascii_fold(text):
    """Strips accents: 'Aleksandar Đorđević' -> 'Aleksandar Dordevic', as the rosters spell it."""
    text = text.translate(NON_DECOMPOSING)
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

def load_previous_players(filename):
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("players", [])

def mark_shared_names(players):
    """Players who share a name get `born` and `pos` so the game can tell them apart.

    Builders hand every player `_born` (YYYY-MM-DD, or YYYY when only the year is known)
    and `_pos`; those are dropped again for everyone with a name of their own.
    """
    counts = defaultdict(int)
    for p in players:
        counts[p["name"].lower()] += 1
    for p in players:
        born, pos = p.pop("_born", None), p.pop("_pos", None)
        if counts[p["name"].lower()] > 1:
            if born:
                p["born"] = born
            if pos:
                p["pos"] = pos


def write_dataset(out_dir, filename, league, teams, players):
    mark_shared_names(players)
    # Same-named players sort by their teams, so reruns write identical files
    players.sort(key=lambda p: (p["name"], p["teams"]))
    countries = sorted({p["country"] for p in players if p["country"]})
    out_path = out_dir / filename
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"league": league, "teams": teams, "countries": countries, "players": players},
                  f, indent=2, ensure_ascii=False)
    print(f"SUCCESS: {out_path} written with {len(players)} players across {len(countries)} countries.")

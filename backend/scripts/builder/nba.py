"""Builds backend/data/nba_data.json.

Every source adds what it knows to one Person per real player: roster snapshots and ESPN
first, then FiveThirtyEight careers, Wikidata, the league's award and playoff history,
and finally the export. DATA.md walks through the rules.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .common import (base_name_key, canonical_country, clean_player_name, load_previous_players, name_key,
                     resolve_birthplace, write_dataset)
from .nba_teams import STANDARD_NBA_TEAMS
from .sources.bbgm import champions_by_season, league_award_winners, load_snapshots
from .sources.espn import load_espn_rosters
from .sources.euroleague_api import fetch_euroleague_people
from .sources.fivethirtyeight import FIVETHIRTYEIGHT_FIRST_SEASON, load_fivethirtyeight
from .sources.wikidata import load_wikidata_players, wikidata_seasons, wikidata_teams

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
    # Wikidata links a same-named foreign town: Horsham (PA, not Australia), Salisbury (NC,
    # not England), Monticello (FL), Bennettsville (SC)
    "Matt Carroll": "USA", "Bobby Jackson": "USA", "Clemon Johnson": "USA", "Cozell McQueen": "USA",
}

US_TERRITORIES = {"Puerto Rico", "U.S. Virgin Islands", "Guam"}

# The same school under the names ESPN and the snapshots use
COLLEGE_ALIASES = {
    "uconn": "Connecticut", "ole miss": "Mississippi", "lsu": "Louisiana State", "usc": "Southern California",
    "unlv": "Nevada-Las Vegas", "nevada las vegas": "Nevada-Las Vegas", "smu": "Southern Methodist",
    "tcu": "Texas Christian", "byu": "Brigham Young", "vcu": "Virginia Commonwealth", "utep": "Texas-El Paso",
    "pitt": "Pittsburgh", "nc state": "North Carolina State", "miami (fl)": "Miami", "miami fl": "Miami",
    "texas a & m": "Texas A&M", "st. john's": "St. John's", "saint john's": "St. John's",
}


@dataclass
class Person:
    born: Optional[int]
    names: list = field(default_factory=list)       # (season, spelling); ESPN names use season 0
    stints: set = field(default_factory=set)        # (season, franchise, playoffs or None)
    teams: set = field(default_factory=set)         # franchises with no known season
    countries: list = field(default_factory=list)   # (season, country)
    colleges: list = field(default_factory=list)    # (season, college)
    drafts: list = field(default_factory=list)      # (season, round, pick); round 0 = undrafted
    awards: set = field(default_factory=set)
    college_only: bool = False                      # birthplace field held a college name
    high_school: bool = False                       # went pro straight from high school
    wikidata_country: Optional[str] = None
    country: Optional[str] = None                   # resolved birth country

    @property
    def name(self):
        return max(self.names)[1]  # latest spelling

    @property
    def franchises(self):
        return self.teams | {team for _, team, _ in self.stints}

    def absorb(self, other):
        self.names += other.names
        self.stints |= other.stints
        self.teams |= other.teams
        self.countries += other.countries
        self.colleges += other.colleges
        self.drafts += other.drafts
        self.awards |= other.awards
        self.college_only |= other.college_only
        self.high_school |= other.high_school


def build_nba_database(out_dir):
    print("Building NBA database...")
    career, season_births, fte_players = load_fivethirtyeight()
    snapshots = load_snapshots()

    people = collect_roster_people(snapshots, season_births)
    add_espn_rosters(people)
    people = merge_roster_duplicates(people)
    add_fivethirtyeight_careers(people, career)

    wikidata = load_wikidata_players()
    matched = match_wikidata(people, wikidata)
    assign_countries(people)
    people += wikidata_only_people(people, wikidata, matched, career)
    people += fivethirtyeight_only_people(people, fte_players)

    history = next((s for s in reversed(snapshots) if s.awards and s.playoff_series), None)
    if history:
        add_league_awards(people, history)
        add_championships(people, champions_by_season(history))

    players = [export_player(p) for p in people]
    players = [p for p in players if p["teams"]]
    write_dataset(out_dir, "nba_data.json", "NBA", STANDARD_NBA_TEAMS, players)


# ---------- Roster snapshots and ESPN ----------

def collect_roster_people(snapshots, season_births):
    """(name_key, birth year) -> Person from every roster snapshot."""
    people = {}
    for snap in snapshots:
        for p in snap.players:
            stints = set()
            if p.get("tid") in snap.teams:
                stints.add((int(snap.season), snap.teams[p["tid"]], False))
            # 2019-20 onwards: the full stats history, mid-season moves and playoff runs included
            for s in p.get("stats", []):
                if s.get("tid") in snap.teams and str(s.get("season", "")).isdigit():
                    stints.add((int(s["season"]), snap.teams[s["tid"]], bool(s.get("playoffs"))))
            if not stints:  # draft prospects and players without NBA games
                continue
            name = clean_player_name(p.get("name") or f"{p.get('firstName', '')} {p.get('lastName', '')}")
            if len(name) < 3:
                continue
            born = p.get("born") or {}
            loc = (born.get("loc") or "").strip()
            if snap.unreliable_bios:
                births = season_births.get((base_name_key(name), snap.season), {})
                birth_year = next(iter(births.values())) if len(births) == 1 else None
            else:
                birth_year = born.get("year")

            person = people.setdefault((name_key(name), birth_year), Person(born=birth_year))
            person.names.append((snap.season, name))
            person.stints |= stints
            country = resolve_birthplace(loc)
            if country:
                person.countries.append((snap.season, country))
            elif loc:
                person.college_only = True
            if HIGH_SCHOOL.search(p.get("college") or ""):
                person.high_school = True
            college = clean_college(p.get("college"))
            if college:
                person.colleges.append((snap.season, college))
            draft = p.get("draft") or {}
            rnd, pick = str(draft.get("round", "")), str(draft.get("pick", ""))
            if rnd.isdigit() and pick.isdigit():  # some files store them as strings
                # The shifted-bio file's draft data is trusted less than any other source
                person.drafts.append((0 if snap.unreliable_bios else snap.season, int(rnd), int(pick)))
            for award in p.get("awards", []):
                if award.get("type") == "Won Championship":
                    person.awards.add("champion")
    return people


def add_espn_rosters(people):
    for e in load_espn_rosters():
        person = people.setdefault((name_key(e.name), e.born), Person(born=e.born))
        # Season 0: the display name stays the familiar roster spelling ('Ron Holland II',
        # not ESPN's 'Ronald Holland II'); ESPN names only show for brand-new players
        person.names.append((0, e.name))
        person.stints.add((e.season, e.team, False))
        country = resolve_birthplace(e.birthplace)
        if country:
            # Lowest priority: ESPN sometimes lists the national team as the birth country
            # (Sandro Mamukelashvili, born in New York, shows up as Georgia)
            person.countries.append((0, country))
        college = clean_college(e.college)
        if college:
            person.colleges.append((0, college))


def clean_college(raw):
    """A school name, or None for blanks and the countries internationals list instead."""
    if not raw:
        return None
    college = raw.strip()
    if canonical_country(college) in KNOWN_COUNTRIES or college.lower() in ("none", "no college"):
        return None
    if HIGH_SCHOOL.search(college):
        return None
    return COLLEGE_ALIASES.get(college.lower(), college)


# Straight-from-high-school players list their school ('St. Vincent-St. Mary HS (OH)'); older
# snapshots drop the 'HS', so one such entry rules out every college for the player
HIGH_SCHOOL = re.compile(r"\b(HS|High School|Academy|Prep)\b")

KNOWN_COUNTRIES = {
    "USA", "Canada", "France", "Spain", "Germany", "Serbia", "Australia", "Croatia", "Lithuania", "Greece",
    "Turkey", "Italy", "Slovenia", "Brazil", "Argentina", "Latvia", "Montenegro", "Nigeria", "Cameroon",
    "Senegal", "Bosnia and Herzegovina", "Czech Republic", "Ukraine", "Russia", "Israel", "Georgia", "Japan",
    "China", "UK", "Finland", "Sweden", "Switzerland", "Austria", "Belgium", "Netherlands", "Poland",
    "Dominican Republic", "Puerto Rico", "New Zealand", "DR Congo", "South Sudan", "Sudan", "Mali", "Angola",
    "Bahamas", "Jamaica", "Haiti", "Mexico", "Venezuela", "Uruguay", "Portugal", "Denmark", "Estonia",
    "North Macedonia", "Republic of the Congo", "Iran", "Egypt", "Tunisia", "Guinea", "Gabon", "Ghana",
    "Cape Verde", "Lebanon", "Philippines", "South Korea", "Taiwan", "Iceland", "Bulgaria", "Romania",
    "Hungary", "Slovakia", "Ireland", "Cyprus", "Belarus", "Kazakhstan", "Ivory Coast", "Burkina Faso",
    "Central African Republic", "Chad", "Tanzania", "Saint Lucia", "Trinidad and Tobago", "U.S. Virgin Islands",
}


def merge_roster_duplicates(people):
    """Merges roster entries that describe the same player.

    Snapshots disagree on details: birth years drift by up to two years, suffixes come
    and go ('Kelly Oubre' / 'Kelly Oubre Jr.'), surnames grow ('Timothe Luwawu' /
    'Timothe Luwawu-Cabarrot') and first names shorten ('Svi' / 'Sviatoslav'). Entries
    without a usable birth year join the only same-named player, if there is one.
    """
    dated = [(key[0], p) for key, p in people.items() if p.born is not None]
    undated = [(key[0], p) for key, p in people.items() if p.born is None]

    parent = list(range(len(dated)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_base = defaultdict(list)
    by_first_two = defaultdict(list)
    by_surname = defaultdict(list)
    for i, (key, _) in enumerate(dated):
        by_base[base_name_key(key)].append(i)
        by_first_two[" ".join(key.split()[:2])].append(i)
        by_surname[" ".join(base_name_key(key).split()[1:])].append(i)

    def same_player(i, j):
        (key_i, a), (key_j, b) = dated[i], dated[j]
        gap = abs(a.born - b.born)
        shared_team = bool(a.franchises & b.franchises)
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
        target = merged.setdefault(root, Person(born=person.born))
        target.absorb(person)
        # Keep the birth year from the most recent snapshot
        if max(person.names) >= max(target.names):
            target.born = person.born

    result = list(merged.values())
    for key, person in undated:
        same = [p for p in result if key in {name_key(n) for _, n in p.names}]
        if len(same) == 1:
            same[0].absorb(person)
        else:
            result.append(person)
    return result


# ---------- FiveThirtyEight and Wikidata ----------

def add_fivethirtyeight_careers(people, career):
    enriched = 0
    for person in people:
        candidates = career.get((base_name_key(person.name), person.born), {}) if person.born else {}
        if len(candidates) == 1:
            stints = next(iter(candidates.values()))
            if not {team for _, team, _ in stints} <= person.franchises:
                enriched += 1
            person.stints |= stints
    print(f"  Career history added teams for {enriched} players")


def match_wikidata(people, wikidata):
    """Links roster players to Wikidata (name + birth year): birth country, pre-1977 stints."""
    index = defaultdict(list)
    for qid, entry in wikidata.items():
        if entry["born"]:
            for year in (entry["born"] - 1, entry["born"], entry["born"] + 1):
                index[(base_name_key(entry["name"]), year)].append(qid)
    matched = set()
    for person in people:
        if not person.born:
            continue
        qids = {qid for _, spelling in person.names for qid in index.get((base_name_key(spelling), person.born), [])}
        if len(qids) != 1:
            continue
        qid = qids.pop()
        entry = wikidata[qid]
        matched.add(qid)
        person.wikidata_country = entry["country"]
        person.teams |= wikidata_teams(entry, before=FIVETHIRTYEIGHT_FIRST_SEASON, include_undated=False)
        person.stints |= {(season, team, None) for season, team in
                          wikidata_seasons(entry, before=FIVETHIRTYEIGHT_FIRST_SEASON)}
    print(f"  Wikidata matched {len(matched)} roster players")
    return matched


def wikidata_only_people(people, wikidata, matched, career):
    """Players no roster snapshot covers (retired before 1995 or between snapshots).

    FiveThirtyEight supplies their 1977+ teams when it knows them. A Wikidata player
    whose name and birth year (within three years) match a roster player is skipped as
    the same person; same-named players further apart are different people.
    """
    known = defaultdict(list)
    for p in people:
        for _, spelling in p.names:
            known[base_name_key(spelling)].append(p.born)
    added = []
    for qid in sorted(wikidata):
        entry = wikidata[qid]
        if qid in matched or not entry["born"]:
            continue
        base = base_name_key(entry["name"])
        if any(b is None or abs(b - entry["born"]) <= 3 for b in known[base]):
            continue
        person = Person(born=entry["born"], names=[(0, entry["name"])])
        stints = career.get((base, entry["born"]), {})
        if len(stints) == 1:
            person.stints |= next(iter(stints.values()))
            person.teams |= wikidata_teams(entry, before=FIVETHIRTYEIGHT_FIRST_SEASON,
                                           include_undated=entry["born"] < 1957)
            person.stints |= {(s, t, None) for s, t in wikidata_seasons(entry, before=FIVETHIRTYEIGHT_FIRST_SEASON)}
        else:
            person.teams |= wikidata_teams(entry)
            person.stints |= {(s, t, None) for s, t in wikidata_seasons(entry)}
        if not person.franchises:
            continue
        if entry["country"]:
            person.countries.append((0, entry["country"]))
        added.append(person)
        known[base].append(entry["born"])
    print(f"  {len(added)} players added from Wikidata")
    return added


def fivethirtyeight_only_people(people, fte_players):
    """1977-2020 players neither the rosters nor Wikidata know (Reggie Jordan).

    FiveThirtyEight has no birthplaces, so their country stays empty and they never
    answer a country criterion.
    """
    known = defaultdict(list)
    for p in people:
        for _, spelling in p.names:
            known[base_name_key(spelling)].append(p.born)
    added = []
    for pid in sorted(fte_players):
        name, born, stints = fte_players[pid]
        base = base_name_key(name)
        if any(b is None or abs(b - born) <= 3 for b in known[base]):
            continue
        added.append(Person(born=born, names=[(0, clean_player_name(name))], stints=set(stints)))
        known[base].append(born)
    print(f"  {len(added)} players added from FiveThirtyEight alone")
    return added


# ---------- Countries ----------

def assign_countries(people):
    """Resolves each roster player's birth country into person.country.

    Wikidata settles foreign birthplaces (Pekovic: Montenegro, not Serbia) and fills gaps,
    but some of its American-born players point at a same-named foreign town (Kendall Gill
    in Paisley, Scotland), and it files Puerto Rico under the USA. A roster USA against a
    Wikidata foreign country is left alone; known cases are in NBA_COUNTRY_OVERRIDES.
    Players with no birthplace fall back to their EuroLeague birth country, a non-default
    country from the previous dataset, then USA when the roster lists an American college.
    """
    euroleague_country = {}
    for entry in fetch_euroleague_people().values():
        if entry["born"] and entry["countries"]:
            for year in (entry["born"] - 1, entry["born"], entry["born"] + 1):
                euroleague_country[(base_name_key(max(entry["names"])[1]), year)] = max(entry["countries"])[1]
    previous_country = {name_key(p["name"]): p.get("country") for p in load_previous_players("nba_data.json")}

    sources = defaultdict(int)
    conflicts = []
    for person in people:
        name = person.name
        country = max(person.countries)[1] if person.countries else None  # newest snapshot wins
        source = "roster"
        wd = person.wikidata_country
        if wd and wd != country:
            if country == "USA" or (wd == "USA" and country in US_TERRITORIES):
                conflicts.append(f"{name} (roster {country}, Wikidata {wd})")
            else:
                country, source = wd, "wikidata" if not country else "wikidata correction"
        if name in NBA_COUNTRY_OVERRIDES:
            country, source = NBA_COUNTRY_OVERRIDES[name], "override"
        elif not country:
            if (base_name_key(name), person.born) in euroleague_country:
                country, source = euroleague_country[(base_name_key(name), person.born)], "euroleague"
            elif previous_country.get(name_key(name)) not in (None, "", "USA", "Georgia"):
                country, source = previous_country[name_key(name)], "previous dataset"
            elif person.college_only:
                country, source = "USA", "US college"
            else:
                country, source = "", "unknown"
        sources[source] += 1
        person.country = country
    print(f"  Country sources: {dict(sources)}")
    if conflicts:
        print(f"  Kept roster country over Wikidata for {len(conflicts)}: {', '.join(conflicts)}")


# ---------- Awards and championships ----------

def add_league_awards(people, snapshot):
    """MVP, Finals MVP, ROY, DPOY, Sixth Man, MIP and All-NBA from the league history.

    Winners are matched by name; when two players share it, by the franchise they won with.
    """
    by_name = defaultdict(list)
    for person in people:
        for key in {name_key(s) for _, s in person.names}:
            by_name[key].append(person)
    by_surname = defaultdict(list)
    for person in people:
        for key in {name_key(s).split()[-1] for _, s in person.names}:
            by_surname[key].append(person)
    unmatched = 0
    for season, award, winner, franchise in league_award_winners(snapshot):
        key = name_key(clean_player_name(winner))
        candidates = by_name.get(key, [])
        if len(candidates) > 1 and franchise:
            candidates = [p for p in candidates if franchise in p.franchises]
        if not candidates and franchise:
            # Known by another first name ('Anfernee' / 'Penny Hardaway'): same surname and
            # on that franchise in the award season
            candidates = [p for p in by_surname.get(key.split()[-1], [])
                          if any(s == season and team == franchise for s, team, _ in p.stints)]
        if len(candidates) == 1:
            candidates[0].awards.add(award)
        else:
            unmatched += 1
    print(f"  League awards: {unmatched} winners could not be matched to one player")


def add_championships(people, champions):
    """A player is a champion when he was on the title team in its playoff run.

    Wikidata season ranges carry no playoff flag; they count for seasons before 1977,
    where they are the only source.
    """
    for person in people:
        for season, team, playoffs in person.stints:
            if champions.get(season) != team:
                continue
            if playoffs or (playoffs is None and season < FIVETHIRTYEIGHT_FIRST_SEASON):
                person.awards.add("champion")
                break
    print(f"  Champions: {sum('champion' in p.awards for p in people)} players, "
          f"{len(champions)} title seasons")


# ---------- Export ----------

def export_player(person):
    country = person.country if person.country is not None else (max(person.countries)[1] if person.countries else "")
    player = {
        "name": person.name,
        # Overrides also cover players who only come from Wikidata
        "country": NBA_COUNTRY_OVERRIDES.get(person.name, country),
        "teams": sorted(person.franchises),
    }
    seasons = [season for season, _, _ in person.stints]
    if seasons:
        player["seasons"] = [min(seasons), max(seasons)]
    if person.awards:
        player["awards"] = sorted(person.awards)
    if person.drafts:
        _, rnd, pick = max(person.drafts)
        player["draft"] = {"round": rnd, "pick": pick}
    if person.colleges and not person.high_school:
        player["college"] = max(person.colleges)[1]
    return player

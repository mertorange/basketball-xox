"""Grid criteria: what a row or column can ask for, and who satisfies it.

Every criterion is a CriterionSpec built from the league's dataset. The board generator
draws from them and the game checks answers against them, so a new kind of criterion only
needs a builder function here.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Tuple

from .players import Player, PlayerCatalog

# Kinds in the order the board prefers them; "team" anchors every grid
TEAM, COUNTRY, COLLEGE, DRAFT, AWARD, CAREER, ERA = "team", "country", "college", "draft", "award", "career", "era"

MIN_COUNTRY_PLAYERS = 3
MIN_COLLEGE_PLAYERS = 20


@dataclass(frozen=True)
class CriterionSpec:
    kind: str
    value: str          # stable key, e.g. "Boston Celtics", "mvp", "decade_1990"
    label: str          # what the grid header shows
    miss: str           # completes "<player> ..." when an answer fails it
    test: Callable[[Player], bool]
    # A player has at most one value of an exclusive kind (one birth country, one
    # college, one draft slot), so two of them can never meet in a box
    exclusive: bool = False

    @property
    def key(self) -> Tuple[str, str]:
        return self.kind, self.value

    def matches(self, player: Player) -> bool:
        return self.test(player)


class CriteriaIndex:
    """All criteria for one league, with the set of matching players precomputed."""

    def __init__(self, catalog: PlayerCatalog, specs: List[CriterionSpec]):
        self.catalog = catalog
        self.specs: Dict[Tuple[str, str], CriterionSpec] = {s.key: s for s in specs}
        self._members: Dict[Tuple[str, str], FrozenSet[int]] = {
            s.key: frozenset(i for i, p in enumerate(catalog.players) if s.matches(p)) for s in specs
        }

    def get(self, kind: str, value: str) -> CriterionSpec:
        return self.specs[(kind, value)]

    def of_kind(self, *kinds: str) -> List[CriterionSpec]:
        return [s for s in self.specs.values() if s.kind in kinds]

    def answer_count(self, a: CriterionSpec, b: CriterionSpec) -> int:
        return len(self._members[a.key] & self._members[b.key])

    def answers(self, a: CriterionSpec, b: CriterionSpec) -> List[Player]:
        return [self.catalog.players[i] for i in sorted(self._members[a.key] & self._members[b.key])]


# ---------- Builders, one per kind ----------

def team_criteria(catalog: PlayerCatalog) -> List[CriterionSpec]:
    return [CriterionSpec(TEAM, team, team, f"did not play for {team}",
                          lambda p, t=team: t in p.get("teams", ()))
            for team in catalog.teams]


def country_criteria(catalog: PlayerCatalog) -> List[CriterionSpec]:
    counts = Counter(p.get("country") for p in catalog.players)
    return [CriterionSpec(COUNTRY, country, country, f"was not born in {country}",
                          lambda p, c=country: p.get("country") == c, exclusive=True)
            for country in catalog.countries if counts[country] >= MIN_COUNTRY_PLAYERS]


def college_criteria(catalog: PlayerCatalog) -> List[CriterionSpec]:
    counts = Counter(p.get("college") for p in catalog.players if p.get("college"))
    return [CriterionSpec(COLLEGE, college, college, f"did not play college ball at {college}",
                          lambda p, c=college: p.get("college") == c, exclusive=True)
            for college, n in sorted(counts.items()) if n >= MIN_COLLEGE_PLAYERS]


def _draft(p: Player) -> Tuple[int, int]:
    d = p.get("draft") or {}
    return d.get("round", -1), d.get("pick", -1)


def draft_criteria() -> List[CriterionSpec]:
    slots = [
        ("first_pick", "#1 overall pick", "was not a #1 overall pick", lambda r, k: r == 1 and k == 1),
        ("top_10", "Top-10 pick", "was not a top-10 pick", lambda r, k: r == 1 and 1 <= k <= 10),
        ("second_round", "Second-round pick", "was not a second-round pick", lambda r, k: r == 2),
        ("undrafted", "Undrafted", "was drafted", lambda r, k: r == 0),
    ]
    # Top-10 contains #1, so these two are not exclusive with each other
    return [CriterionSpec(DRAFT, value, label, miss, lambda p, f=rule: f(*_draft(p)),
                          exclusive=value in ("second_round", "undrafted"))
            for value, label, miss, rule in slots]


def award_criteria(awards: List[Tuple[str, str, str]]) -> List[CriterionSpec]:
    return [CriterionSpec(AWARD, value, label, miss, lambda p, a=value: a in p.get("awards", ()))
            for value, label, miss in awards]


def career_stat_criteria(thresholds: List[Tuple[str, int, str]]) -> List[CriterionSpec]:
    return [CriterionSpec(CAREER, f"{stat}_{minimum}", label, f"does not have {label[0].lower()}{label[1:]}",
                          lambda p, s=stat, m=minimum: (p.get("stats") or {}).get(s, 0) >= m)
            for stat, minimum, label in thresholds]


def franchise_count_criterion(minimum: int, noun: str) -> CriterionSpec:
    label = f"Played for {minimum}+ {noun}"
    return CriterionSpec(CAREER, f"franchises_{minimum}", label, f"did not play for {minimum}+ {noun}",
                         lambda p: len(p.get("teams", ())) >= minimum)


def _played_in_decade(p: Player, decade: int) -> bool:
    """Seasons are named after the year they end; 1989-90 belongs to the 1980s."""
    seasons = p.get("seasons")
    if not seasons:
        return False
    first_start, last_start = seasons[0] - 1, seasons[1] - 1
    return first_start <= decade + 9 and last_start >= decade


def era_criteria(decades: List[int]) -> List[CriterionSpec]:
    # 'Played 1980-89' rather than '1980s': grid headers are set in capitals ('1980S')
    return [CriterionSpec(ERA, f"decade_{d}", f"Played {d}–{str(d + 9)[-2:]}",
                          f"did not play in {d}–{str(d + 9)[-2:]}", lambda p, d=d: _played_in_decade(p, d))
            for d in decades]


# ---------- Per league ----------

NBA_AWARDS = [
    ("champion", "NBA champion", "never won an NBA title"),
    ("mvp", "MVP", "never won MVP"),
    ("finals_mvp", "Finals MVP", "never won Finals MVP"),
    ("all_nba", "All-NBA team", "never made an All-NBA team"),
    ("roy", "Rookie of the Year", "was not Rookie of the Year"),
    ("dpoy", "Defensive Player of the Year", "never won Defensive Player of the Year"),
    ("sixth_man", "Sixth Man of the Year", "never won Sixth Man of the Year"),
    ("mip", "Most Improved Player", "never won Most Improved Player"),
]
EUROLEAGUE_AWARDS = [
    ("champion", "EuroLeague champion", "never won the EuroLeague"),
    ("final_four", "Played a Final Four", "never played a Final Four"),
]
EUROLEAGUE_CAREER = [
    ("points", 1000, "1,000+ EuroLeague points"), ("games", 150, "150+ EuroLeague games"),
    ("assists", 300, "300+ EuroLeague assists"), ("rebounds", 500, "500+ EuroLeague rebounds"),
]


def build_index(catalog: PlayerCatalog) -> CriteriaIndex:
    specs = team_criteria(catalog) + country_criteria(catalog)
    if catalog.league == "nba":
        specs += college_criteria(catalog) + draft_criteria() + award_criteria(NBA_AWARDS)
        specs += [franchise_count_criterion(5, "franchises")]
        specs += era_criteria([1960, 1970, 1980, 1990, 2000, 2010, 2020])
    else:
        specs += award_criteria(EUROLEAGUE_AWARDS) + career_stat_criteria(EUROLEAGUE_CAREER)
        specs += [franchise_count_criterion(3, "EuroLeague clubs")]
        specs += era_criteria([2000, 2010, 2020])
    return CriteriaIndex(catalog, specs)

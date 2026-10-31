"""Grid generation: three row and three column criteria at a chosen difficulty.

Difficulty is counted in well-known answers (about the top 10% of a league by fame, see
catalog/fame.py): a box with forty answers who all had short bench careers is hard, one
whose few answers include a superstar is easy. Each level sets the range of well-known
answers every box must fall in, and among the grids that fit, the generator keeps the one
whose boxes are closest to each other, so a grid never mixes a giveaway with a box nobody
can fill. A level the data can't meet is loosened a step at a time.
"""

import math
import random
from dataclasses import dataclass, replace
from typing import Dict, FrozenSet, List, Optional, Tuple

from ..catalog.criteria import COUNTRY, ERA, TEAM, TEAMMATE, CriteriaIndex, CriterionSpec
from ..catalog.fame import is_well_known

ATTEMPTS = 3000      # grids drawn per search
CANDIDATES = 25      # grids that fit the level, out of which the most even one is kept

DIFFICULTIES = ("easy", "medium", "hard")

# Share of mixed grids built around one decade at levels with decade_turns
DECADE_SHARE = 0.3
DECADE_ATTEMPTS = 800     # grids drawn per step of a decade grid
DECADE_OVER_CAP = 4       # how far a decade's boxes may go over the level's cap, as a multiple

# Share of mixed grids where "Played with" may appear. Its boxes fit every level so easily
# that, left to an equal draw, it would be in three grids out of four.
TEAMMATE_SHARE = 0.2

# A country's players are spread thin: Italy has answers at most clubs but few well-known
# ones, so it can't fill three boxes of an ordinary grid. In a country's turn its own boxes
# need one well-known answer among at least three.
BIG_COUNTRY_PLAYERS = 50    # players a country needs to get turns of its own
COUNTRY_BOX_KNOWN = 1
COUNTRY_BOX_TOTAL = 3


@dataclass(frozen=True)
class Level:
    min_known: int             # well-known answers every box needs
    max_known: Optional[int]   # and at most this many; None for no cap
    min_total: int             # answers of any fame every box needs
    # Mixed grids: (non-team rows, non-team columns) to draw from. Columns stay mostly teams
    # so every grid reads like a team sheet; rows carry the twists. Harder levels use more.
    layouts: Tuple[Tuple[int, int], ...]
    # Eras only appear in grids built around one decade, chosen evenly. A team has too many
    # well-known players from recent decades for an ordinary draw to fit a tight cap, so
    # only the oldest decades would ever survive it.
    decade_turns: bool = False
    # Share of grids built around one big basketball country
    country_share: float = 0.0


EASY_LAYOUTS = ((1, 0), (2, 0))
MEDIUM_LAYOUTS = ((2, 0), (2, 0), (3, 0), (2, 1))
HARD_LAYOUTS = ((2, 1), (3, 0), (3, 1))

# The EuroLeague has fewer players, so its boxes are smaller at the same difficulty
LEVELS: Dict[str, Dict[str, Level]] = {
    "nba": {
        "easy": Level(min_known=8, max_known=None, min_total=8, layouts=EASY_LAYOUTS),
        "medium": Level(min_known=3, max_known=30, min_total=4, layouts=MEDIUM_LAYOUTS),
        "hard": Level(min_known=1, max_known=6, min_total=3, layouts=HARD_LAYOUTS, decade_turns=True),
    },
    "euroleague": {
        "easy": Level(min_known=6, max_known=None, min_total=6, layouts=EASY_LAYOUTS, country_share=0.2),
        "medium": Level(min_known=2, max_known=25, min_total=4, layouts=MEDIUM_LAYOUTS, country_share=0.2),
        # Its twists (eras, Final Four) hold most of its well-known players, so a hard
        # EuroLeague grid leans on club pairs and uses fewer of them
        "hard": Level(min_known=1, max_known=6, min_total=3, layouts=((1, 0), (1, 1), (2, 0)), decade_turns=True,
                      country_share=0.2),
    },
}

# When the data is too thin even for a loosened level (a small test set): any grid where
# every box has an answer
FALLBACK = Level(min_known=0, max_known=None, min_total=1, layouts=MEDIUM_LAYOUTS)


def loosened(level: Level) -> List[Level]:
    """The level, then with its cap doubled; the floor stays, so a hard grid stays hard-ish."""
    steps = [level]
    if level.max_known is not None:
        steps.append(replace(level, max_known=level.max_known * 2))
    return steps

Board = Tuple[List[CriterionSpec], List[CriterionSpec]]


class BoardGenerator:
    def __init__(self, index: CriteriaIndex, rng: Optional[random.Random] = None):
        self.index = index
        self.rng = rng or random.Random()
        self.levels = LEVELS.get(index.catalog.league, LEVELS["nba"])
        self.teams = index.of_kind(TEAM)
        self.countries = index.of_kind(COUNTRY)
        self.big_countries = [spec for spec in self.countries
                              if index.answer_count(spec, spec) >= BIG_COUNTRY_PLAYERS]
        self.other_kinds = sorted({s.kind for s in index.specs.values()} - {TEAM})
        self.by_kind = {kind: index.of_kind(kind) for kind in self.other_kinds}
        self._usable_cache: Dict[Tuple[str, Level], List[CriterionSpec]] = {}
        players = index.catalog.players
        league = index.catalog.league
        known = frozenset(i for i, p in enumerate(players) if is_well_known(league, p))
        self.known: Dict[Tuple[str, str], FrozenSet[int]] = {
            key: members & known for key, members in index.members().items()
        }

    def generate(self, style: str = "mixed", difficulty: str = "medium",
                 categories: Optional[List[str]] = None) -> Board:
        """The most even grid that fits the level. If none does: the level loosened, then a
        classic grid at the level (better than an easier mixed one), then any solvable grid.

        style "custom" uses only the non-team kinds in `categories` (teams are always in).
        One chosen kind leads each grid, in fair turns, and the grid must include it, so every
        tick shows up whatever the difficulty. The level gives way before the tick does; if
        even that fails it falls back to teams alone, never to unchosen kinds.
        """
        level = self.levels[difficulty]
        levels = loosened(level)
        wants_country = style != "custom" or COUNTRY in (categories or ())
        if wants_country and self.rng.random() < level.country_share:
            board = self._country_grid(level)
            if board:
                return board
        if style == "custom":
            chosen = [kind for kind in self.other_kinds if kind in set(categories or ())]
            lead = self.rng.choice(chosen) if chosen else None
            if level.decade_turns and ERA in chosen:
                if lead == ERA:
                    board = self._decade_grid(level, [kind for kind in chosen if kind != ERA])
                    if board:
                        return board
                # Otherwise eras wait for their turn, unless they are all that was ticked
                chosen = [kind for kind in chosen if kind != ERA] or chosen
                lead = lead if lead in chosen else self.rng.choice(chosen)
            tries = [("custom", chosen, level, lead) for level in levels + [FALLBACK]]
            tries += [("custom", [], level, None) for level in levels + [FALLBACK]]
        else:
            kinds = self.other_kinds
            if style == "mixed" and self.rng.random() >= TEAMMATE_SHARE:
                kinds = [kind for kind in kinds if kind != TEAMMATE]
            if style == "mixed" and level.decade_turns and ERA in kinds:
                kinds = [kind for kind in kinds if kind != ERA]
                if self.rng.random() < DECADE_SHARE:
                    board = self._decade_grid(level, kinds)
                    if board:
                        return board
            styles = [(style, kinds)] + ([("classic", None)] if style == "mixed" else [])
            tries = [(st, kinds, level, None) for st, kinds in styles for level in levels]
            tries += [(st, kinds, FALLBACK, None) for st, kinds in styles]
        for st, kinds, level, lead_kind in tries:
            board = self._search(st, level, kinds, lead_kind)
            if board:
                return board
        raise RuntimeError("No solvable grid found")

    def _search(self, style: str, level: Level, kinds: Optional[List[str]] = None,
                lead: Optional[str] = None) -> Optional[Board]:
        fits = []
        for _ in range(ATTEMPTS):
            if style == "classic":
                rows, cols = self._draw_classic()
            else:
                # Mixed grids take each kind at most once; a custom one may repeat a chosen kind
                rows, cols = self._draw_mixed(level.layouts, kinds, style == "mixed", level, lead)
            known = self._known_counts(rows, cols, level)
            if known is not None:
                fits.append((self._spread(known), rows, cols))
                if len(fits) >= CANDIDATES:
                    break
        return self._most_even(fits)

    @staticmethod
    def _most_even(fits) -> Optional[Board]:
        if not fits:
            return None
        _, rows, cols = min(fits, key=lambda fit: fit[0])
        return rows, cols

    def _decade_grid(self, level: Level, twists: List[str]) -> Optional[Board]:
        """A grid around one decade, every decade equally likely. Crossed with teams, a
        recent decade has far more well-known answers than a hard box may, so it faces
        narrow criteria in the columns (MVP, Undrafted). Failing that its own boxes may go
        over the cap, a little and then freely, with teams in the columns if need be: the
        rest of the grid stays hard, and the decade still gets its turn."""
        decade = self.rng.choice(self.by_kind[ERA])
        # Only teams with a well-known player from that decade (few had one in the 1960s)
        with_decade = [team for team in self.teams if self.known[decade.key] & self.known[team.key]]
        if len(with_decade) < 6:
            return None
        over = level.max_known * DECADE_OVER_CAP
        steps = [(step, step.max_known, (2, 3)) for step in loosened(level)]
        steps += [(level, over, (2, 3)), (level, over, (0, 1)), (level, None, (0, 1, 2, 3))]
        for step, decade_cap, narrow_counts in steps:
            fits = []
            for _ in range(DECADE_ATTEMPTS):
                rows = [decade] + self.rng.sample(self.teams, 2)
                self.rng.shuffle(rows)
                narrow = self._draw_others(self.rng.choice(narrow_counts), twists, False)
                teams = [team for team in with_decade if team not in rows]
                cols = narrow + self.rng.sample(teams, 3 - len(narrow))
                self.rng.shuffle(cols)
                known = self._known_counts(rows, cols, step, decade, decade_cap)
                if known is not None:
                    fits.append((self._spread(known), rows, cols))
                    if len(fits) >= CANDIDATES:
                        break
            board = self._most_even(fits)
            if board:
                return board
        return None

    def _country_grid(self, level: Level) -> Optional[Board]:
        """A grid around one big country, each equally likely, against clubs it has answers
        at. The other boxes keep to the level; the country's may go over its cap if they must."""
        if not self.big_countries:
            return None
        country = self.rng.choice(self.big_countries)
        clubs = [team for team in self.teams
                 if self.index.answer_count(country, team) >= COUNTRY_BOX_TOTAL
                 and len(self.known[country.key] & self.known[team.key]) >= COUNTRY_BOX_KNOWN]
        if len(clubs) < 3:
            return None
        over = level.max_known and level.max_known * DECADE_OVER_CAP
        for step, cap in [(step, step.max_known) for step in loosened(level)] + [(level, over), (level, None)]:
            fits = []
            for _ in range(DECADE_ATTEMPTS):
                cols = self.rng.sample(clubs, 3)
                rows = [country] + self.rng.sample([team for team in self.teams if team not in cols], 2)
                self.rng.shuffle(rows)
                known = self._known_counts(rows, cols, step, country, cap, thin=True)
                if known is not None:
                    fits.append((self._spread(known), rows, cols))
                    if len(fits) >= CANDIDATES:
                        break
            board = self._most_even(fits)
            if board:
                return board
        return None

    def _known_counts(self, rows, cols, level: Level, special: Optional[CriterionSpec] = None,
                      special_cap: Optional[int] = None, thin: bool = False) -> Optional[List[int]]:
        """Well-known answers per box, or None when a box falls outside the level. Boxes of
        the `special` criterion have `special_cap` as their cap instead (None: no cap), and
        with `thin` the country box minimums too."""
        counts = []
        for r in rows:
            for c in cols:
                if r.key == c.key or (r.exclusive and c.exclusive and r.kind == c.kind):
                    return None
                known = len(self.known[r.key] & self.known[c.key])
                is_special = special is not None and special in (r, c)
                cap = special_cap if is_special else level.max_known
                min_known, min_total = level.min_known, level.min_total
                if is_special and thin:
                    min_known, min_total = COUNTRY_BOX_KNOWN, COUNTRY_BOX_TOTAL
                if known < min_known or (cap is not None and known > cap):
                    return None
                if self.index.answer_count(r, c) < min_total:
                    return None
                counts.append(known)
        return counts

    @staticmethod
    def _spread(known: List[int]) -> float:
        # On a log scale: 2 against 6 well-known answers is as uneven as 20 against 60
        return math.log1p(max(known)) - math.log1p(min(known))

    def is_solvable(self, rows: List[CriterionSpec], cols: List[CriterionSpec], target: int) -> bool:
        """Every box has at least `target` answers of any fame."""
        return self._known_counts(rows, cols, Level(0, None, max(target, 0), ())) is not None

    def box_counts(self, rows: List[CriterionSpec], cols: List[CriterionSpec]) -> List[Tuple[int, int]]:
        """(answers, well-known answers) for each box, row by row."""
        return [(self.index.answer_count(r, c), len(self.known[r.key] & self.known[c.key]))
                for r in rows for c in cols]

    def _draw_classic(self) -> Board:
        """Teams, with a birth country on one row most of the time."""
        if self.countries and self.rng.random() < 0.6:
            teams = self.rng.sample(self.teams, 5)
            rows = teams[:2] + [self.rng.choice(self.countries)]
            self.rng.shuffle(rows)
            return rows, teams[2:]
        teams = self.rng.sample(self.teams, 6)
        return teams[:3], teams[3:]

    def _draw_mixed(self, layouts, kinds: List[str], distinct: bool = True, level: Optional[Level] = None,
                    lead: Optional[str] = None) -> Board:
        other_rows, other_cols = self.rng.choice(layouts)
        others = self._draw_others(other_rows + other_cols, kinds, distinct, level, lead)
        # Fewer twists than the layout asks for (few kinds to draw from): rows keep theirs first
        other_rows = min(other_rows, len(others))
        other_cols = len(others) - other_rows
        teams = self.rng.sample(self.teams, 6 - len(others))
        rows = others[:other_rows] + teams[:3 - other_rows]
        cols = others[other_rows:] + teams[3 - other_rows:]
        self.rng.shuffle(rows)
        self.rng.shuffle(cols)
        return rows, cols

    def _draw_others(self, count: int, kinds: List[str], distinct: bool, level: Optional[Level] = None,
                     lead: Optional[str] = None) -> List[CriterionSpec]:
        """Non-team criteria, each kind equally likely, so a league with many colleges does
        not crowd out awards. distinct: one per kind. Otherwise (custom grids) the lead kind
        comes first, then every other chosen kind, and only then do kinds come back with a
        different criterion (MVP and Rookie of the Year); only criteria that can fit the
        level are drawn, so a kind with few of them still gets its turn."""
        if not kinds:
            return []
        if distinct:
            picks = self.rng.sample(kinds, min(count, len(kinds)))
        else:
            rest = [kind for kind in kinds if kind != lead]
            self.rng.shuffle(rest)
            picks = ([lead] if lead else []) + rest
            picks += [self.rng.choice(kinds) for _ in range(max(0, count - len(picks)))]
            picks = picks[:count]
        chosen: List[CriterionSpec] = []
        for kind in picks:
            pool = self._usable(kind, level) if not distinct and level else self.by_kind[kind]
            options = [spec for spec in pool if spec not in chosen]
            if options:
                chosen.append(self.rng.choice(options))
        return chosen

    def _usable(self, kind: str, level: Level) -> List[CriterionSpec]:
        """Criteria of a kind that fit the level against at least three teams (a full row or
        column); all of them when none does, so the kind is never silently empty."""
        key = (kind, level)
        if key not in self._usable_cache:
            fit = [spec for spec in self.by_kind[kind]
                   if sum(self._known_counts([spec], [team], level) is not None for team in self.teams) >= 3]
            self._usable_cache[key] = fit or self.by_kind[kind]
        return self._usable_cache[key]

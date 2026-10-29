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

from ..catalog.criteria import COUNTRY, TEAM, CriteriaIndex, CriterionSpec
from ..catalog.fame import is_well_known

ATTEMPTS = 3000      # grids drawn per search
CANDIDATES = 25      # grids that fit the level, out of which the most even one is kept

DIFFICULTIES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class Level:
    min_known: int             # well-known answers every box needs
    max_known: Optional[int]   # and at most this many; None for no cap
    min_total: int             # answers of any fame every box needs
    # Mixed grids: (non-team rows, non-team columns) to draw from. Columns stay mostly teams
    # so every grid reads like a team sheet; rows carry the twists. Harder levels use more.
    layouts: Tuple[Tuple[int, int], ...]


EASY_LAYOUTS = ((1, 0), (2, 0))
MEDIUM_LAYOUTS = ((2, 0), (2, 0), (3, 0), (2, 1))
HARD_LAYOUTS = ((2, 1), (3, 0), (3, 1))

# The EuroLeague has fewer players, so its boxes are smaller at the same difficulty
LEVELS: Dict[str, Dict[str, Level]] = {
    "nba": {
        "easy": Level(min_known=8, max_known=None, min_total=8, layouts=EASY_LAYOUTS),
        "medium": Level(min_known=3, max_known=30, min_total=4, layouts=MEDIUM_LAYOUTS),
        "hard": Level(min_known=1, max_known=6, min_total=3, layouts=HARD_LAYOUTS),
    },
    "euroleague": {
        "easy": Level(min_known=6, max_known=None, min_total=6, layouts=EASY_LAYOUTS),
        "medium": Level(min_known=2, max_known=25, min_total=4, layouts=MEDIUM_LAYOUTS),
        # Its twists (eras, Final Four) hold most of its well-known players, so a hard
        # EuroLeague grid leans on club pairs and uses fewer of them
        "hard": Level(min_known=1, max_known=6, min_total=3, layouts=((1, 0), (1, 1), (2, 0))),
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
        self.other_kinds = sorted({s.kind for s in index.specs.values()} - {TEAM})
        self.by_kind = {kind: index.of_kind(kind) for kind in self.other_kinds}
        players = index.catalog.players
        league = index.catalog.league
        known = frozenset(i for i, p in enumerate(players) if is_well_known(league, p))
        self.known: Dict[Tuple[str, str], FrozenSet[int]] = {
            key: members & known for key, members in index.members().items()
        }

    def generate(self, style: str = "mixed", difficulty: str = "medium") -> Board:
        """The most even grid that fits the level. If none does: the level loosened, then a
        classic grid at the level (better than an easier mixed one), then any solvable grid."""
        styles = [style, "classic"] if style == "mixed" else [style]
        tries = [(st, level) for st in styles for level in loosened(self.levels[difficulty])]
        tries += [(st, FALLBACK) for st in styles]
        for st, level in tries:
            board = self._search(st, level)
            if board:
                return board
        raise RuntimeError("No solvable grid found")

    def _search(self, style: str, level: Level) -> Optional[Board]:
        fits = []
        for _ in range(ATTEMPTS):
            rows, cols = self._draw_mixed(level.layouts) if style == "mixed" else self._draw_classic()
            known = self._known_counts(rows, cols, level)
            if known is not None:
                fits.append((self._spread(known), rows, cols))
                if len(fits) >= CANDIDATES:
                    break
        if not fits:
            return None
        _, rows, cols = min(fits, key=lambda fit: fit[0])
        return rows, cols

    def _known_counts(self, rows, cols, level: Level) -> Optional[List[int]]:
        """Well-known answers per box, or None when a box falls outside the level."""
        counts = []
        for r in rows:
            for c in cols:
                if r.key == c.key or (r.exclusive and c.exclusive and r.kind == c.kind):
                    return None
                known = len(self.known[r.key] & self.known[c.key])
                if known < level.min_known or (level.max_known is not None and known > level.max_known):
                    return None
                if self.index.answer_count(r, c) < level.min_total:
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

    def _draw_mixed(self, layouts) -> Board:
        other_rows, other_cols = self.rng.choice(layouts)
        # A league with fewer kinds than the layout asks for gets fewer twists
        other_rows = min(other_rows, len(self.other_kinds))
        other_cols = min(other_cols, len(self.other_kinds) - other_rows)
        others = self._draw_others(other_rows + other_cols)
        teams = self.rng.sample(self.teams, 6 - len(others))
        rows = others[:other_rows] + teams[:3 - other_rows]
        cols = others[other_rows:] + teams[3 - other_rows:]
        self.rng.shuffle(rows)
        self.rng.shuffle(cols)
        return rows, cols

    def _draw_others(self, count: int) -> List[CriterionSpec]:
        """Non-team criteria from distinct kinds, each kind equally likely, so a league
        with many colleges does not crowd out awards."""
        kinds = self.rng.sample(self.other_kinds, count)
        return [self.rng.choice(self.by_kind[kind]) for kind in kinds]

"""Grid generation: three row and three column criteria where every box has answers."""

import random
from typing import List, Optional, Tuple

from ..catalog.criteria import COUNTRY, TEAM, CriteriaIndex, CriterionSpec

ATTEMPTS_PER_TARGET = 4000

# Mixed grids: where the non-team criteria go. Columns stay mostly teams so every grid
# reads like a team sheet; rows carry the twists.
MIXED_LAYOUTS = [
    # (non-team rows, non-team columns)
    (2, 0),
    (2, 0),
    (3, 0),
    (2, 1),
]

Board = Tuple[List[CriterionSpec], List[CriterionSpec]]


class BoardGenerator:
    def __init__(self, index: CriteriaIndex, rng: Optional[random.Random] = None):
        self.index = index
        self.rng = rng or random.Random()
        self.teams = index.of_kind(TEAM)
        self.countries = index.of_kind(COUNTRY)
        self.other_kinds = sorted({s.kind for s in index.specs.values()} - {TEAM})
        self.by_kind = {kind: index.of_kind(kind) for kind in self.other_kinds}

    def generate(self, style: str = "mixed", min_answers: int = 2) -> Board:
        """Tries the requested density first, then relaxes it, then falls back to classic."""
        for target in sorted({min_answers, max(1, min_answers - 1), 1}, reverse=True):
            for _ in range(ATTEMPTS_PER_TARGET):
                rows, cols = self._draw_mixed() if style == "mixed" else self._draw_classic()
                if self.is_solvable(rows, cols, target):
                    return rows, cols
        if style == "mixed":
            return self.generate("classic", min_answers)
        raise RuntimeError("No solvable grid found")

    def is_solvable(self, rows: List[CriterionSpec], cols: List[CriterionSpec], target: int) -> bool:
        for r in rows:
            for c in cols:
                if r.key == c.key or (r.exclusive and c.exclusive and r.kind == c.kind):
                    return False
                if self.index.answer_count(r, c) < target:
                    return False
        return True

    def _draw_classic(self) -> Board:
        """Teams, with a birth country on one row most of the time."""
        if self.countries and self.rng.random() < 0.6:
            teams = self.rng.sample(self.teams, 5)
            rows = teams[:2] + [self.rng.choice(self.countries)]
            self.rng.shuffle(rows)
            return rows, teams[2:]
        teams = self.rng.sample(self.teams, 6)
        return teams[:3], teams[3:]

    def _draw_mixed(self) -> Board:
        other_rows, other_cols = self.rng.choice(MIXED_LAYOUTS)
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
        kinds = self.rng.sample(self.other_kinds, min(count, len(self.other_kinds)))
        return [self.rng.choice(self.by_kind[kind]) for kind in kinds]

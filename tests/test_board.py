import random

import pytest

from backend.catalog.criteria import TEAM, build_index
from backend.catalog.players import PlayerCatalog
from backend.game.board import BoardGenerator


def test_generated_board_is_solvable(nba_index):
    generator = BoardGenerator(nba_index, rng=random.Random(1))
    rows, cols = generator.generate("classic", min_answers=1)
    assert len(rows) == len(cols) == 3
    assert generator.is_solvable(rows, cols, 1)


def test_exclusive_kinds_never_meet(nba_index):
    generator = BoardGenerator(nba_index)
    undrafted = nba_index.get("draft", "undrafted")
    second_round = nba_index.get("draft", "second_round")
    teams = nba_index.of_kind(TEAM)
    assert not generator.is_solvable([undrafted] + teams[:2], [second_round] + teams[2:4], 0)


@pytest.mark.parametrize("league", ["nba", "euroleague"])
@pytest.mark.parametrize("style", ["classic", "mixed"])
def test_real_data_boards(league, style):
    catalog = PlayerCatalog.load(league)
    if not catalog.players:
        pytest.skip("dataset not built")
    index = build_index(catalog)
    generator = BoardGenerator(index, rng=random.Random(3))
    kinds = set()
    for _ in range(20):
        rows, cols = generator.generate(style, min_answers=2)
        assert generator.is_solvable(rows, cols, 1)
        kinds |= {s.kind for s in rows + cols}
    if style == "mixed":
        assert len(kinds) >= 4, kinds
    else:
        assert kinds <= {"team", "country"}

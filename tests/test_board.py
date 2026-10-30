import random

import pytest

from backend.catalog.criteria import TEAM, build_index
from backend.catalog.players import PlayerCatalog
from backend.game.board import DIFFICULTIES, LEVELS, BoardGenerator, Level


def test_generated_board_is_solvable(nba_index):
    generator = BoardGenerator(nba_index, rng=random.Random(1))
    rows, cols = generator.generate("classic")
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
        rows, cols = generator.generate(style, "medium")
        assert generator.is_solvable(rows, cols, 1)
        kinds |= {s.kind for s in rows + cols}
    if style == "mixed":
        assert len(kinds) >= 4, kinds
    else:
        assert kinds <= {"team", "country"}


@pytest.mark.parametrize("league", ["nba", "euroleague"])
def test_real_data_difficulty_levels(league):
    """Every box keeps the level's floor of well-known answers, and the levels really differ."""
    catalog = PlayerCatalog.load(league)
    if not catalog.players:
        pytest.skip("dataset not built")
    index = build_index(catalog)
    medians = {}
    for difficulty in DIFFICULTIES:
        generator = BoardGenerator(index, rng=random.Random(8))
        level = LEVELS[league][difficulty]
        known = []
        for _ in range(15):
            rows, cols = generator.generate("mixed", difficulty)
            counts = [k for _, k in generator.box_counts(rows, cols)]
            assert min(counts) >= level.min_known, (difficulty, counts)
            if level.max_known is not None:
                # At most loosened once; a decade's own boxes may go further at Hard
                pairs = [(r, c) for r in rows for c in cols]
                others = [k for k, (r, c) in zip(counts, pairs) if not (level.decade_turns and "era" in (r.kind, c.kind))]
                assert max(others) <= 2 * level.max_known, (difficulty, counts)
            known += counts
        medians[difficulty] = sorted(known)[len(known) // 2]
    assert medians["easy"] > medians["medium"] > medians["hard"], medians


def test_levels_cap_and_floor_well_known_answers(nba_index):
    """On the sample data, Celtics x Lakers has one well-known answer (Alpha One)."""
    for p in nba_index.catalog.players:
        p["fame"] = 100 if p["name"] == "Alpha One" else 0
    generator = BoardGenerator(nba_index)
    celtics, lakers = nba_index.get(TEAM, "Boston Celtics"), nba_index.get(TEAM, "Los Angeles Lakers")
    bulls, heat = nba_index.get(TEAM, "Chicago Bulls"), nba_index.get(TEAM, "Miami Heat")
    assert generator.box_counts([celtics], [lakers]) == [(1, 1)]
    one_known = Level(min_known=1, max_known=None, min_total=1, layouts=())
    assert generator._known_counts([celtics], [lakers], one_known) == [1]
    assert generator._known_counts([bulls], [heat], one_known) is None        # Gamma, Delta: not well known
    no_stars = Level(min_known=0, max_known=0, min_total=1, layouts=())
    assert generator._known_counts([celtics], [lakers], no_stars) is None    # over the cap
    assert generator._known_counts([bulls], [heat], no_stars) == [0]


def test_thin_data_falls_back_to_a_solvable_grid(nba_index):
    # Six sample players can't meet any level; the generator still deals a playable grid
    generator = BoardGenerator(nba_index, rng=random.Random(2))
    for difficulty in DIFFICULTIES:
        rows, cols = generator.generate("mixed", difficulty)
        assert generator.is_solvable(rows, cols, 1)


def test_custom_grids_use_only_the_chosen_categories(nba_index):
    generator = BoardGenerator(nba_index, rng=random.Random(5))
    for categories in (["award"], ["award", "draft"], []):
        for _ in range(5):
            rows, cols = generator.generate("custom", "medium", categories)
            assert generator.is_solvable(rows, cols, 1)
            assert {s.kind for s in rows + cols} <= {TEAM, *categories}


def test_custom_ignores_categories_the_league_lacks(nba_index):
    generator = BoardGenerator(nba_index, rng=random.Random(6))
    generator.other_kinds = [k for k in generator.other_kinds if k != "college"]  # as in the EuroLeague
    rows, cols = generator.generate("custom", "medium", ["college"])
    assert {s.kind for s in rows + cols} == {TEAM}


@pytest.mark.parametrize("league,categories", [("nba", ["award"]), ("nba", ["era", "draft"]),
                                               ("euroleague", ["career"])])
def test_real_data_custom_grids(league, categories):
    catalog = PlayerCatalog.load(league)
    if not catalog.players:
        pytest.skip("dataset not built")
    generator = BoardGenerator(build_index(catalog), rng=random.Random(4))
    used = set()
    for _ in range(8):
        rows, cols = generator.generate("custom", "medium", categories)
        kinds = {s.kind for s in rows + cols}
        assert kinds <= {TEAM, *categories}
        used |= kinds
    assert used - {TEAM}, "the chosen categories never showed up"


@pytest.mark.parametrize("league,categories", [("nba", ["country", "college", "draft", "award", "career", "era"]),
                                               ("euroleague", ["country", "award", "career", "era"])])
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_real_data_custom_grids_give_every_tick_a_turn(league, categories, difficulty):
    catalog = PlayerCatalog.load(league)
    if not catalog.players:
        pytest.skip("dataset not built")
    generator = BoardGenerator(build_index(catalog), rng=random.Random(9))
    seen = set()
    for _ in range(30):
        rows, cols = generator.generate("custom", difficulty, categories)
        seen |= {s.kind for s in rows + cols}
    assert set(categories) <= seen, set(categories) - seen


@pytest.mark.parametrize("league", ["nba", "euroleague"])
def test_real_data_every_decade_gets_a_turn_at_hard(league):
    catalog = PlayerCatalog.load(league)
    if not catalog.players:
        pytest.skip("dataset not built")
    index = build_index(catalog)
    generator = BoardGenerator(index, rng=random.Random(6))
    seen = set()
    for _ in range(40):
        rows, cols = generator.generate("custom", "hard", ["era"])
        seen |= {s.key for s in rows + cols if s.kind == "era"}
    assert seen == {s.key for s in index.of_kind("era")}

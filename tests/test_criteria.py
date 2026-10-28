from backend.catalog.criteria import AWARD, COLLEGE, COUNTRY, DRAFT, ERA, TEAM


def names(players):
    return sorted(p["name"] for p in players)


def test_team_and_country(nba_index):
    celtics = nba_index.get(TEAM, "Boston Celtics")
    usa = nba_index.get(COUNTRY, "USA")
    assert names(nba_index.answers(celtics, usa)) == ["Alpha One", "Beta Two", "Twin Name"]
    assert celtics.miss == "did not play for Boston Celtics"
    assert usa.miss == "was not born in USA"


def test_award_and_draft(nba_index):
    champion = nba_index.get(AWARD, "champion")
    first_pick = nba_index.get(DRAFT, "first_pick")
    top_10 = nba_index.get(DRAFT, "top_10")
    second_round = nba_index.get(DRAFT, "second_round")
    undrafted = nba_index.get(DRAFT, "undrafted")
    celtics = nba_index.get(TEAM, "Boston Celtics")
    assert names(nba_index.answers(champion, celtics)) == ["Alpha One", "Beta Two"]
    assert names(nba_index.answers(first_pick, celtics)) == ["Alpha One"]
    assert nba_index.answer_count(top_10, first_pick) == 1
    assert names(nba_index.answers(second_round, celtics)) == ["Beta Two"]
    assert names(nba_index.answers(undrafted, nba_index.get(TEAM, "Miami Heat"))) == ["Gamma Three"]


def test_unknown_draft_matches_nothing(nba_index):
    delta = next(p for p in nba_index.catalog.players if p["name"] == "Delta Four")
    for value in ("first_pick", "top_10", "second_round", "undrafted"):
        assert not nba_index.get(DRAFT, value).matches(delta)


def test_decades_use_the_season_start_year(nba_index):
    nineties = nba_index.get(ERA, "decade_1990")
    eighties = nba_index.get(ERA, "decade_1980")
    delta = next(p for p in nba_index.catalog.players if p["name"] == "Delta Four")  # 1988-89 .. 1998-99
    assert nineties.matches(delta) and eighties.matches(delta)
    gamma = next(p for p in nba_index.catalog.players if p["name"] == "Gamma Three")  # 2014-15 .. 2023-24
    assert not nineties.matches(gamma)
    assert nba_index.get(ERA, "decade_2020").matches(gamma)


def test_franchise_count(nba_index):
    five = nba_index.get("career", "franchises_5")
    assert names(p for p in nba_index.catalog.players if five.matches(p)) == ["Delta Four"]


def test_small_colleges_and_countries_are_not_criteria(nba_index):
    # The sample has two Duke players, below the threshold for a college criterion
    assert not nba_index.of_kind(COLLEGE)
    assert {s.value for s in nba_index.of_kind(COUNTRY)} == {"USA"}  # France has 2 players


def test_exclusive_kinds(nba_index):
    assert nba_index.get(DRAFT, "undrafted").exclusive
    assert not nba_index.get(DRAFT, "top_10").exclusive
    assert not nba_index.get(TEAM, "Miami Heat").exclusive

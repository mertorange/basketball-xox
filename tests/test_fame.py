import pytest

from backend.catalog.fame import WELL_KNOWN, assign_fame, is_well_known
from backend.catalog.players import PlayerCatalog


def nba_player(name, pages=None, minutes=0, awards=(), draft=None):
    p = {"name": name, "country": "USA", "teams": ["Boston Celtics"], "stats": {"minutes": minutes}}
    if pages is not None:
        p["wiki_pages"] = pages
    if awards:
        p["awards"] = list(awards)
    if draft:
        p["draft"] = draft
    return p


def test_nba_fame_orders_stars_over_journeymen():
    players = [
        nba_player("Star", pages=90, minutes=40000, awards=["mvp", "all_nba", "champion"]),
        nba_player("Cult hero", pages=35, minutes=3000),
        nba_player("Journeyman", pages=8, minutes=15000),
        nba_player("Cup of coffee", pages=2, minutes=40),
    ]
    assign_fame("nba", players)
    fame = {p["name"]: p["fame"] for p in players}
    assert fame["Star"] == 100 and fame["Cup of coffee"] == 0
    assert fame["Star"] > fame["Cult hero"] > fame["Journeyman"] > fame["Cup of coffee"]


def test_nba_missing_pages_come_from_players_with_similar_minutes():
    players = [nba_player(f"Vet {i}", pages=40, minutes=30000) for i in range(3)]
    players += [nba_player(f"Bench {i}", pages=3, minutes=500) for i in range(3)]
    players.append(nba_player("Unmatched vet", minutes=30000))   # no Wikidata match
    assign_fame("nba", players)
    by_name = {p["name"]: p["fame"] for p in players}
    assert by_name["Unmatched vet"] == by_name["Vet 0"]


def test_top_draft_pick_counts_before_playing():
    players = [nba_player("No. 1 pick", pages=20, draft={"round": 1, "pick": 1}),
               nba_player("Second-rounder", pages=20, draft={"round": 2, "pick": 1})]
    assign_fame("nba", players)
    assert players[0]["fame"] > players[1]["fame"]


def test_euroleague_fame_uses_league_stats_and_hand_list():
    players = [
        {"name": "Legend", "seasons": [2005, 2020], "awards": ["champion", "final_four"],
         "stats": {"games": 400, "points": 5000}},
        {"name": "Role player", "seasons": [2015, 2018], "stats": {"games": 80, "points": 300}},
        {"name": "Registered, never played", "seasons": [2020, 2020]},
        {"name": "Zeljko Rebraca"},   # before the stats start: on the hand list
    ]
    assign_fame("euroleague", players)
    fame = {p["name"]: p["fame"] for p in players}
    assert fame["Zeljko Rebraca"] == 100
    assert fame["Legend"] > fame["Role player"] > fame["Registered, never played"]


def test_catalog_assigns_fame_and_threshold():
    catalog = PlayerCatalog("nba", {"players": [nba_player("A", pages=50), nba_player("B", pages=1)]})
    a, b = catalog.players
    assert (a["fame"], b["fame"]) == (100, 0)
    assert is_well_known("nba", a) and not is_well_known("nba", b)
    assert WELL_KNOWN["nba"] > WELL_KNOWN["euroleague"]  # the NBA's pool is bigger, so its cut is higher


@pytest.mark.parametrize("league", ["nba", "euroleague"])
def test_real_data_passes_the_refresh_fame_checks(league):
    from refresh_data import fame_problems
    catalog = PlayerCatalog.load(league)
    if not catalog.players:
        pytest.skip("dataset not built")
    assert fame_problems(league, catalog) == []

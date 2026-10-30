from builder.common import base_name_key, canonical_country, name_key, resolve_birthplace
from builder.sources.euroleague_api import format_euroleague_name


def test_name_keys():
    assert name_key("R.J. Barrett") == name_key("RJ Barrett") == name_key("R. J. Barrett")
    assert name_key("A. C. Green") == name_key("A.C. Green")
    assert name_key("Luka Dončić") == "luka doncic"
    assert base_name_key("Kelly Oubre Jr.") == "kelly oubre"
    assert base_name_key("Gary Payton II") == "gary payton"


def test_birthplaces():
    assert resolve_birthplace("Akron, OH") == "USA"
    assert resolve_birthplace("Tbilisi, Georgia") == "Georgia"
    assert resolve_birthplace("Georgia Tech") is None  # a college, not a place
    assert resolve_birthplace("Melbourne, Australia - Country: USA") == "Australia"
    assert resolve_birthplace("Kinshasa, Congo") == "DR Congo"
    assert canonical_country("Türkiye") == "Turkey"
    assert canonical_country("United States of America") == "USA"


def test_euroleague_names():
    assert format_euroleague_name("MCCORMACK, DAVID") == "David McCormack"
    assert format_euroleague_name("O'NEALE, ROYCE") == "Royce O'Neale"


def test_only_shared_names_keep_birth_date_and_position():
    from builder.common import mark_shared_names
    players = [
        {"name": "Mike James", "_born": "1990-08-18", "_pos": "PG"},
        {"name": "Mike James", "_born": "1975", "_pos": None},
        {"name": "Luka Doncic", "_born": "1999-02-28", "_pos": "G"},
    ]
    mark_shared_names(players)
    assert players[0] == {"name": "Mike James", "born": "1990-08-18", "pos": "PG"}
    assert players[1] == {"name": "Mike James", "born": "1975"}
    assert players[2] == {"name": "Luka Doncic"}


def test_records_of_one_player_merge_into_one():
    from builder.aliases import apply_aliases
    players = [
        {"name": "Metta World Peace", "country": "USA", "teams": ["Chicago Bulls"], "seasons": [2000, 2017],
         "awards": ["dpoy"], "stats": {"games": 900, "minutes": 30000}},
        {"name": "Ron Artest", "country": "", "teams": ["Los Angeles Lakers"], "seasons": [2010, 2010],
         "awards": ["champion"], "stats": {"games": 77, "minutes": 2000}, "wiki_pages": 40},
    ]
    apply_aliases("nba", players)
    assert len(players) == 1
    player = players[0]
    assert player["teams"] == ["Chicago Bulls", "Los Angeles Lakers"] and player["seasons"] == [2000, 2017]
    assert player["awards"] == ["champion", "dpoy"] and player["country"] == "USA"
    assert player["stats"] == {"games": 900, "minutes": 30000}  # overlapping sources are not added up
    assert player["wiki_pages"] == 40 and "Ron Artest" in player["aliases"]
    apply_aliases("nba", players)  # safe to run on data that is already merged
    assert len(players) == 1


def test_a_merge_can_pick_one_of_two_same_named_players():
    from builder.aliases import apply_aliases
    players = [{"name": "Patrick Ewing", "country": "USA", "teams": ["New York Knicks"]},
               {"name": "Patrick Ewing", "country": "USA", "teams": ["New Orleans Pelicans"]},
               {"name": "Patrick Ewing, Jr.", "country": "USA", "teams": ["Sacramento Kings"]}]
    apply_aliases("nba", players)
    assert len(players) == 2
    knicks, son = players
    assert "aliases" not in knicks and son["teams"] == ["New Orleans Pelicans", "Sacramento Kings"]

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

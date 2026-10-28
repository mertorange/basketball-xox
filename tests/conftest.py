import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from backend.catalog.criteria import build_index  # noqa: E402
from backend.catalog.players import PlayerCatalog  # noqa: E402
from backend.game.board import BoardGenerator  # noqa: E402
from backend.game.manager import GameManager  # noqa: E402

TEAMS = ["Boston Celtics", "Los Angeles Lakers", "Chicago Bulls", "Miami Heat", "Golden State Warriors",
         "San Antonio Spurs"]


def _player(name, country, teams, **extra):
    return {"name": name, "country": country, "teams": teams, **extra}


SAMPLE_NBA = {
    "league": "NBA",
    "teams": TEAMS,
    "countries": ["France", "USA"],
    "players": [
        _player("Alpha One", "USA", ["Boston Celtics", "Los Angeles Lakers"], awards=["champion", "mvp"],
                draft={"round": 1, "pick": 1}, college="Duke", seasons=[1995, 2005]),
        _player("Beta Two", "USA", ["Boston Celtics", "Chicago Bulls"], awards=["champion"],
                draft={"round": 2, "pick": 5}, college="Duke", seasons=[2001, 2012]),
        _player("Gamma Three", "France", ["Miami Heat", "Los Angeles Lakers", "Chicago Bulls"],
                draft={"round": 0, "pick": 0}, seasons=[2015, 2024]),
        _player("Delta Four", "France", ["Golden State Warriors", "San Antonio Spurs", "Miami Heat",
                                         "Boston Celtics", "Chicago Bulls"], seasons=[1989, 1999]),
        _player("Twin Name", "USA", ["Boston Celtics"]),
        _player("Twin Name", "USA", ["Miami Heat"], awards=["mvp"]),
    ],
}


@pytest.fixture
def nba_catalog():
    return PlayerCatalog("nba", SAMPLE_NBA)


@pytest.fixture
def nba_index(nba_catalog):
    return build_index(nba_catalog)


@pytest.fixture
def manager(nba_index):
    m = GameManager({"nba": nba_index})
    m.generators["nba"] = BoardGenerator(nba_index, rng=random.Random(7))
    return m

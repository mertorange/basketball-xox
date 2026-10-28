from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import build_router


def make_client(manager):
    app = FastAPI()
    app.include_router(build_router(manager))
    return TestClient(app)


def test_search_returns_names_only(manager):
    client = make_client(manager)
    res = client.get("/api/search-players", params={"q": "twin", "league": "nba"})
    assert res.status_code == 200
    assert res.json() == [{"name": "Twin Name"}]


def test_game_round_trip(manager):
    client = make_client(manager)
    game = client.post("/api/new-game", json={"league": "nba", "min_answers": 1, "grid_style": "classic"}).json()
    assert len(game["row_criteria"]) == 3
    assert client.get(f"/api/game/{game['game_id']}").status_code == 200
    assert client.get("/api/game/missing").status_code == 404
    bad = client.post("/api/new-game", json={"league": "nba", "min_answers": 9})
    assert bad.status_code == 422

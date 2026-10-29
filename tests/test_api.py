from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import build_router
from backend.catalog.criteria import TEAM
from backend.game.manager import to_criterion


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


def test_answers_only_after_the_game(manager, nba_index):
    client = make_client(manager)
    game_id = client.post("/api/new-game", json={"league": "nba", "min_answers": 1,
                                                 "grid_style": "classic"}).json()["game_id"]
    game = manager.get_game(game_id)
    game.row_criteria = [to_criterion(nba_index.get(TEAM, t)) for t in
                         ("Boston Celtics", "Chicago Bulls", "Miami Heat")]
    game.col_criteria = [to_criterion(nba_index.get(TEAM, t)) for t in
                         ("Los Angeles Lakers", "Boston Celtics", "Chicago Bulls")]
    assert client.get(f"/api/game/{game_id}/answers").status_code == 409

    assert manager.make_move(game_id, 0, 0, "Alpha One").success
    manager.forfeit(game_id, "O")
    res = client.get(f"/api/game/{game_id}/answers")
    assert res.status_code == 200
    cells = res.json()["cells"]
    assert len(cells) == 3 and all(len(row) == 3 for row in cells)
    first = cells[0][0]
    assert first["row"] == "Boston Celtics" and first["col"] == "Los Angeles Lakers"
    assert first["answers"] == ["Alpha One"] and first["count"] == 1
    assert first["picked"] == "Alpha One" and first["claimed_by"] == "X"
    # Celtics x Celtics: the award winner (Alpha One) comes before the others
    assert cells[0][1]["answers"][0] == "Alpha One" and cells[0][1]["count"] == 4
    assert client.get("/api/game/missing/answers").status_code == 404

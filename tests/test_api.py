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
    game = client.post("/api/new-game", json={"league": "nba", "grid_style": "classic"}).json()
    assert len(game["row_criteria"]) == 3
    assert client.get(f"/api/game/{game['game_id']}").status_code == 200
    assert client.get("/api/game/missing").status_code == 404
    bad = client.post("/api/new-game", json={"league": "nba", "difficulty": "impossible"})
    assert bad.status_code == 422


def test_answers_only_after_the_game(manager, nba_index):
    client = make_client(manager)
    game_id = client.post("/api/new-game", json={"league": "nba",
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


def test_skip_turn_and_draw(manager):
    client = make_client(manager)
    game_id = client.post("/api/new-game", json={"league": "nba", "grid_style": "classic",
                                                 "first_player": "X"}).json()["game_id"]
    res = client.post("/api/skip-turn", json={"game_id": game_id})
    assert res.status_code == 200 and res.json()["current_player"] == "O"

    drawn = client.post("/api/draw", json={"game_id": game_id}).json()
    assert drawn["status"] == "finished" and drawn["winner"] == "DRAW"
    assert client.post("/api/skip-turn", json={"game_id": game_id}).status_code == 409
    assert client.post("/api/draw", json={"game_id": game_id}).status_code == 409
    assert client.post("/api/draw", json={"game_id": "missing"}).status_code == 404


def test_same_device_routes_refuse_online_games(manager):
    client = make_client(manager)
    game = manager.create_game("nba", grid_style="classic", online=True)
    gid = {"game_id": game.game_id}
    for path in ("/api/skip-turn", "/api/draw", "/api/shot-clock-violation"):
        assert client.post(path, json=gid).status_code == 409
    move = client.post("/api/move", json={**gid, "row": 0, "col": 0, "player_name": "Nobody"})
    assert move.status_code == 409
    assert game.status == "in_progress" and game.current_player == "X"
    assert all(cell.claimed_by is None for row in game.grid for cell in row)
    # Reading the state is still fine: spectators already get it over the socket
    assert client.get(f"/api/game/{game.game_id}").status_code == 200


def test_same_device_moves_and_clock(manager):
    client = make_client(manager)
    game_id = client.post("/api/new-game", json={"league": "nba",
                                                 "grid_style": "classic"}).json()["game_id"]
    move = client.post("/api/move", json={"game_id": game_id, "row": 0, "col": 0, "player_name": "Nobody"})
    assert move.status_code == 200 and "not found" in move.json()["message"]
    clock = client.post("/api/shot-clock-violation", json={"game_id": game_id})
    assert clock.status_code == 200 and clock.json()["current_player"] == "X"
    missing = {"game_id": "missing", "row": 0, "col": 0, "player_name": "Nobody"}
    assert client.post("/api/move", json=missing).status_code == 404
    assert client.post("/api/shot-clock-violation", json={"game_id": "missing"}).status_code == 404
    assert client.get(f"/api/cell-info/{game_id}/0/0").status_code == 404  # removed: it leaked answer counts


def test_custom_grid_categories(manager):
    client = make_client(manager)
    game = client.post("/api/new-game", json={"league": "nba", "grid_style": "custom",
                                               "categories": ["award"]}).json()
    assert game["grid_style"] == "custom" and game["categories"] == ["award"]
    assert {c["type"] for c in game["row_criteria"] + game["col_criteria"]} <= {"team", "award"}
    # Categories only count for custom grids
    mixed = client.post("/api/new-game", json={"league": "nba", "categories": ["award"]}).json()
    assert mixed["categories"] is None
    bad = client.post("/api/new-game", json={"league": "nba", "grid_style": "custom", "categories": ["team"]})
    assert bad.status_code == 422

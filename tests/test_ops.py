import json
import os

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.app import create_app
from backend.catalog.criteria import build_index
from backend.catalog.players import DATA_DIR, PlayerCatalog
from backend.ratelimit import RateLimiter
from refresh_data import prune, switch_current, validate

from conftest import SAMPLE_NBA


def test_rate_limiter_slides_over_a_minute():
    now = [0.0]
    limiter = RateLimiter({("POST", "/api/rooms"): 2}, clock=lambda: now[0])
    assert limiter.allow("1.1.1.1", "POST", "/api/rooms")
    assert limiter.allow("1.1.1.1", "POST", "/api/rooms")
    assert not limiter.allow("1.1.1.1", "POST", "/api/rooms")
    assert limiter.allow("2.2.2.2", "POST", "/api/rooms")       # per client
    assert limiter.allow("1.1.1.1", "GET", "/api/game/x")        # unlimited route
    now[0] = 61
    assert limiter.allow("1.1.1.1", "POST", "/api/rooms")


def test_game_keeps_its_data_after_a_reload(manager, nba_catalog):
    game = manager.create_game("nba", grid_style="classic")
    old_index = manager.index_for(game)
    smaller = dict(SAMPLE_NBA, players=SAMPLE_NBA["players"][:4])
    manager.replace_indexes({"nba": build_index(PlayerCatalog("nba", smaller))})
    assert manager.index_for(game) is old_index
    assert manager.create_game("nba", grid_style="classic") is not None
    assert len(manager.indexes["nba"].catalog.players) == 4


def test_prune_keeps_live_games(manager):
    a = manager.create_game("nba", grid_style="classic")
    b = manager.create_game("nba", grid_style="classic")
    assert manager.prune(-1, keep={b.game_id}) == 1
    assert manager.get_game(a.game_id) is None and manager.get_game(b.game_id) is not None


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "secret")
    with TestClient(create_app()) as client:
        yield client


def test_health_and_reload(app_client):
    health = app_client.get("/health").json()
    assert health["status"] == "ok" and health["players"]["nba"] > 0
    assert app_client.post("/admin/reload").status_code == 403
    assert app_client.post("/admin/reload", headers={"X-Admin-Token": "wrong"}).status_code == 403
    res = app_client.post("/admin/reload", headers={"X-Admin-Token": "secret"})
    assert res.status_code == 200 and res.json()["players"] == health["players"]


def test_release_switch_and_prune(tmp_path):
    releases = tmp_path / "releases"
    for stamp in ["20260101-000000", "20260102-000000", "20260103-000000"]:
        (releases / stamp).mkdir(parents=True)
    switch_current(tmp_path, releases / "20260102-000000")
    assert os.readlink(tmp_path / "current") == "releases/20260102-000000"
    switch_current(tmp_path, releases / "20260103-000000")
    assert (tmp_path / "current").resolve() == (releases / "20260103-000000").resolve()
    prune(releases, keep=1, live=releases / "20260103-000000")
    assert sorted(p.name for p in releases.iterdir()) == ["20260103-000000"]


def test_validate_rejects_a_broken_release(tmp_path):
    current = tmp_path / "current"
    release = tmp_path / "release"
    current.mkdir()
    release.mkdir()
    for path in (current, release):
        (path / "nba_data.json").write_text(json.dumps(SAMPLE_NBA))
        (path / "euroleague_data.json").write_text(json.dumps({"teams": [], "players": []}))
    problems = validate(release, current)
    assert any("nba: only 6 players" in p for p in problems)
    assert any("euroleague: only 0 players" in p for p in problems)


def test_validate_accepts_the_shipped_data():
    if not (DATA_DIR / "nba_data.json").exists():
        pytest.skip("dataset not built")
    assert validate(DATA_DIR, DATA_DIR) == []

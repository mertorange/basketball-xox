import json
import os

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.app import create_app
from backend.catalog.criteria import build_index
from backend.catalog.players import DATA_DIR, PlayerCatalog
from backend.ratelimit import RateLimiter
from refresh_data import IMAGE_MARKER, prune, publish_image_data, switch_current, validate

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


def can_symlink(path):
    """Windows only lets admins and Developer Mode create symlinks."""
    try:
        (path / "link").symlink_to("target")
    except OSError:
        return False
    (path / "link").unlink()
    return True


def test_release_switch_and_prune(tmp_path):
    if not can_symlink(tmp_path):
        pytest.skip("this account can't create symlinks")
    releases = tmp_path / "releases"
    for age, stamp in enumerate(["20260101-000000", "20260102-000000", "20260103-000000"]):
        (releases / stamp).mkdir(parents=True)
        os.utime(releases / stamp, (1_000_000 + age, 1_000_000 + age))  # prune goes by age
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


def test_rate_limiter_counts_every_room_code_together():
    limiter = RateLimiter({("GET", "/api/rooms/*"): 2, ("POST", "/api/rooms"): 1})
    assert limiter.allow("1.1.1.1", "GET", "/api/rooms/AAAA")
    assert limiter.allow("1.1.1.1", "GET", "/api/rooms/BBBB")
    assert not limiter.allow("1.1.1.1", "GET", "/api/rooms/CCCC")
    assert limiter.allow("1.1.1.1", "POST", "/api/rooms")       # the exact route counts apart


def test_rate_limiter_forgets_old_clients():
    now = [0.0]
    limiter = RateLimiter({("GET", "/x"): 5}, clock=lambda: now[0])
    for client in ("1.1.1.1", "2.2.2.2"):
        limiter.allow(client, "GET", "/x")
    now[0] = 61.0
    limiter.allow("3.3.3.3", "GET", "/x")
    assert [key[0] for key in limiter.hits] == ["3.3.3.3"]


@pytest.fixture
def limited_client(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(config, "RATE_LIMITS", {("GET", "/api/rooms/*"): 2, ("WS", "/ws/rooms/*"): 2,
                                                ("WS", "message"): 2})
    with TestClient(create_app()) as client:
        yield client


def test_room_lookups_are_limited_across_codes(limited_client):
    assert [limited_client.get(f"/api/rooms/AAA{i}").status_code for i in range(3)] == [404, 404, 429]


def test_room_joins_are_limited(limited_client):
    reasons = []
    for _ in range(3):
        with limited_client.websocket_connect("/ws/rooms/NONE") as socket:
            reasons.append(socket.receive_json()["reason"])
    assert reasons == ["No room with that code."] * 2 + ["Too many joins, try again in a minute."]


def test_room_messages_are_limited(limited_client):
    code = limited_client.post("/api/rooms", json={}).json()["code"]
    with limited_client.websocket_connect(f"/ws/rooms/{code}") as socket:
        socket.send_json({"type": "join", "name": "Ann"})
        while socket.receive_json()["type"] != "room":
            pass
        reasons = []
        for _ in range(3):
            socket.send_json({"type": "nonsense"})
            reasons.append(socket.receive_json()["reason"])
    assert reasons == ["Malformed message."] * 2 + ["Too many messages, slow down a little."]


def image_folder(path, nba_players):
    path.mkdir(parents=True, exist_ok=True)
    (path / "nba_data.json").write_text(json.dumps({**SAMPLE_NBA, "players": nba_players}))
    (path / "euroleague_data.json").write_text(json.dumps({"teams": [], "players": []}))
    return path


def test_image_data_is_published_once_per_image(tmp_path):
    """First start and image updates publish the image's data; restarts keep refreshed data."""
    if not can_symlink(tmp_path):
        pytest.skip("this account can't create symlinks")
    root = tmp_path / "data"
    image_v1 = image_folder(tmp_path / "image-v1", SAMPLE_NBA["players"][:3])

    first = publish_image_data(root, image_v1)
    assert first and first.startswith("image-")
    assert (root / "current").resolve() == (root / "releases" / first).resolve()
    assert json.loads((root / "current" / "nba_data.json").read_text())["players"] == SAMPLE_NBA["players"][:3]

    # A data refresh publishes a dated release; restarting the same image must keep it
    refreshed = image_folder(root / "releases" / "20261101-050000", SAMPLE_NBA["players"])
    switch_current(root, refreshed)
    assert publish_image_data(root, image_v1) is None
    assert (root / "current").resolve() == refreshed.resolve()

    # A new image (new code, maybe new fields) brings new data: that goes live
    image_v2 = image_folder(tmp_path / "image-v2", SAMPLE_NBA["players"][:4])
    second = publish_image_data(root, image_v2)
    assert second and second != first
    assert (root / "current").resolve() == (root / "releases" / second).resolve()
    assert (root / IMAGE_MARKER).read_text() == second.removeprefix("image-")


def test_volumes_from_before_the_marker_take_the_image_data(tmp_path):
    """A volume seeded by the old entrypoint has no marker: the image's data replaces it."""
    if not can_symlink(tmp_path):
        pytest.skip("this account can't create symlinks")
    root = tmp_path / "data"
    old = image_folder(root / "releases" / "seed", SAMPLE_NBA["players"][:2])
    switch_current(root, old)
    published = publish_image_data(root, image_folder(tmp_path / "image", SAMPLE_NBA["players"]))
    assert published and (root / "current").resolve() == (root / "releases" / published).resolve()

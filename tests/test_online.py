import time
from contextlib import ExitStack

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.catalog.criteria import TEAM
from backend.game.manager import to_criterion
from backend.online.rooms import RoomManager
from backend.online.ws import build_online_router
from backend.ratelimit import RateLimiter

ROWS = [(TEAM, "Boston Celtics"), (TEAM, "Chicago Bulls"), (TEAM, "Miami Heat")]
COLS = [(TEAM, "Los Angeles Lakers"), (TEAM, "Boston Celtics"), (TEAM, "Chicago Bulls")]


@pytest.fixture
def online(manager):
    rooms = RoomManager(manager, disconnect_grace=0.3)
    app = FastAPI()
    app.include_router(build_online_router(rooms, RateLimiter({})))
    with TestClient(app) as client, ExitStack() as sockets:
        client.sockets = sockets  # every socket a test opens is closed, even when it fails
        yield client, rooms, manager


def create_room(client, shot_clock=0):
    res = client.post("/api/rooms", json={"league": "nba", "shot_clock": shot_clock,
                                          "grid_style": "classic"})
    assert res.status_code == 200
    return res.json()["code"]


def recv_until(ws, predicate, limit=20):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("expected message never arrived")


def room_msg(ws, predicate=lambda m: True):
    return recv_until(ws, lambda m: m["type"] == "room" and predicate(m))


def drop(ws):
    """Closes a connection the way a closed tab would."""
    if not getattr(ws, "dropped", False):
        ws.dropped = True
        ws.__exit__(None, None, None)


def join(client, code, name, token=None):
    ws = client.websocket_connect(f"/ws/rooms/{code}")
    ws.__enter__()
    client.sockets.callback(drop, ws)
    ws.send_json({"type": "join", "name": name, "token": token})
    welcome = recv_until(ws, lambda m: m["type"] in ("welcome", "error"))
    return ws, welcome


def start_match(client, rooms, manager, shot_clock=0):
    """Two seated players, both ready, on a known board."""
    code = create_room(client, shot_clock)
    a, wa = join(client, code, "Ann")
    b, wb = join(client, code, "Ben")
    a.send_json({"type": "ready"})
    b.send_json({"type": "ready"})
    room_msg(a, lambda m: m["phase"] == "playing")
    room_msg(b, lambda m: m["phase"] == "playing")
    room = rooms.get(code)
    game = manager.get_game(room.game_id)
    index = manager.indexes["nba"]
    game.row_criteria = [to_criterion(index.get(*k)) for k in ROWS]
    game.col_criteria = [to_criterion(index.get(*k)) for k in COLS]
    return code, room, a, b, wa, wb


def test_room_codes_and_seats(online):
    client, rooms, _ = online
    code = create_room(client)
    assert len(code) == 4 and code.isalpha() and not set(code) & set("ILO")
    assert client.get(f"/api/rooms/{code.lower()}").json()["phase"] == "waiting"
    assert client.get("/api/rooms/ZZZZ").status_code == 404

    a, wa = join(client, code, "Ann")
    b, wb = join(client, code, "Ben")
    c, wc = join(client, code, "Cal")
    assert (wa["seat"], wb["seat"]) == ("X", "O")
    assert wc == {"type": "error", "reason": "This room is full."}
    snapshot = room_msg(b, lambda m: len(m["seats"]) == 2)
    assert snapshot["phase"] == "lobby" and snapshot["you"] == "O"
    assert snapshot["seats"]["X"]["name"] == "Ann"


def test_turns_moves_and_turnovers(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)

    b.send_json({"type": "pick", "row": 0, "col": 0, "name": "Alpha One"})
    assert recv_until(b, lambda m: m["type"] == "error")["reason"] == "It is not your turn."

    a.send_json({"type": "focus", "row": 1, "col": 1})
    assert room_msg(b, lambda m: m["focus"] is not None)["focus"] == {"row": 1, "col": 1}

    a.send_json({"type": "pick", "row": 0, "col": 0, "name": "alpha one"})
    event = recv_until(b, lambda m: m["type"] == "event" and m["kind"] == "move")
    assert event["mark"] == "X" and event["player"] == "Alpha One"
    snap = room_msg(b, lambda m: m["game"]["current_player"] == "O")
    assert snap["game"]["grid"][0][0]["claimed_by"] == "X" and snap["focus"] is None

    b.send_json({"type": "pick", "row": 0, "col": 0, "name": "Beta Two"})  # taken: no turnover
    assert "already claimed" in recv_until(b, lambda m: m["type"] == "error")["reason"]
    b.send_json({"type": "pick", "row": 2, "col": 2, "name": "Nobody"})
    assert recv_until(a, lambda m: m["type"] == "event" and m["kind"] == "turnover")["mark"] == "O"
    assert room_msg(a, lambda m: m["game"]["current_player"] == "X")


def test_win_rematch_and_alternating_start(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    for ws, row, col, name in [(a, 0, 0, "Alpha One"), (b, 1, 0, "Gamma Three"), (a, 0, 1, "Beta Two"),
                               (b, 2, 0, "Nobody"), (a, 0, 2, "Delta Four")]:
        ws.send_json({"type": "pick", "row": row, "col": col, "name": name})
        recv_until(ws, lambda m: m["type"] == "room" and m["game"]["used_players"] is not None)
    final = room_msg(b, lambda m: m["phase"] == "final")
    assert final["scores"] == {"X": 1, "O": 0} and final["game"]["winner"] == "X"

    a.send_json({"type": "rematch"})
    assert room_msg(b, lambda m: m["seats"]["X"]["rematch"])["phase"] == "final"
    b.send_json({"type": "rematch"})
    snap = room_msg(a, lambda m: m["phase"] == "playing" and m["game"]["game_id"] != final["game"]["game_id"])
    assert snap["game"]["current_player"] == "O"  # starts alternate between games
    assert snap["scores"] == {"X": 1, "O": 0}


def test_server_shot_clock(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager, shot_clock=1)
    snap = room_msg(a)
    assert 0 < snap["turn_ms_left"] <= 1000
    event = recv_until(b, lambda m: m["type"] == "event" and m["kind"] == "violation")
    assert event["mark"] == "X"
    assert room_msg(b, lambda m: m["game"]["current_player"] == "O")


def test_reconnect_keeps_the_seat(online):
    client, rooms, manager = online
    code, room, a, b, wa, _ = start_match(client, rooms, manager)
    drop(a)
    assert recv_until(b, lambda m: m["type"] == "event" and m["kind"] == "disconnected")["mark"] == "X"
    a2, welcome = join(client, code, "Someone else", token=wa["token"])
    assert welcome["seat"] == "X"
    snap = room_msg(a2)
    assert snap["seats"]["X"]["name"] == "Ann" and snap["phase"] == "playing"
    time.sleep(0.5)  # longer than the grace period: the cancelled forfeit must not fire
    assert manager.get_game(room.game_id).status == "in_progress"


def test_disconnect_forfeits_after_grace(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    drop(a)
    event = recv_until(b, lambda m: m["type"] == "event" and m["kind"] == "forfeit")
    assert event["mark"] == "X"
    final = room_msg(b, lambda m: m["phase"] == "final")
    assert final["game"]["winner"] == "O" and final["scores"]["O"] == 1


def test_leave_mid_game(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    b.send_json({"type": "leave"})
    assert recv_until(a, lambda m: m["type"] == "event" and m["kind"] == "left")["mark"] == "O"
    snap = room_msg(a, lambda m: "O" not in m["seats"])
    assert snap["game"]["winner"] == "X" and snap["scores"]["X"] == 1


def watch(client, code):
    ws = client.websocket_connect(f"/ws/rooms/{code}")
    ws.__enter__()
    client.sockets.callback(drop, ws)
    ws.send_json({"type": "join", "role": "spectator"})
    return ws, recv_until(ws, lambda m: m["type"] in ("welcome", "error"))


def test_spectators_watch_but_cannot_play(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    s, welcome = watch(client, code)
    assert welcome == {"type": "welcome", "token": None, "seat": None}
    snap = room_msg(s, lambda m: m["phase"] == "playing")
    assert snap["you"] is None and snap["spectators"] == 1
    assert room_msg(a, lambda m: m["spectators"] == 1)

    s.send_json({"type": "pick", "row": 0, "col": 0, "name": "Alpha One"})
    assert recv_until(s, lambda m: m["type"] == "error")["reason"] == "Spectators can watch but not play."

    a.send_json({"type": "focus", "row": 2, "col": 1})
    assert room_msg(s, lambda m: m["focus"] is not None)["focus"] == {"row": 2, "col": 1}
    a.send_json({"type": "pick", "row": 0, "col": 0, "name": "Alpha One"})
    assert recv_until(s, lambda m: m["type"] == "event" and m["kind"] == "move")["player"] == "Alpha One"

    drop(s)
    assert room_msg(a, lambda m: m["spectators"] == 0)
    assert len(room.seats) == 2  # watching never takes a seat


def test_spectator_limit(online, monkeypatch):
    from backend.online import rooms as rooms_module
    client, rooms, _ = online
    monkeypatch.setattr(rooms_module, "MAX_SPECTATORS", 1)
    code = create_room(client)
    _, first = watch(client, code)
    _, second = watch(client, code)
    assert first["type"] == "welcome"
    assert second == {"type": "error", "reason": "This room has as many spectators as it can take."}


def test_skip_turn(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    b.send_json({"type": "skip"})
    assert recv_until(b, lambda m: m["type"] == "error")["reason"] == "It is not your turn."

    a.send_json({"type": "skip"})
    event = recv_until(b, lambda m: m["type"] == "event" and m["kind"] == "skip")
    assert event["mark"] == "X"
    assert room_msg(b, lambda m: m["game"]["current_player"] == "O")


def test_draw_offer_declined_then_accepted(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    first_game = room.game_id

    a.send_json({"type": "answer_draw", "accept": True})  # nothing to answer yet
    assert "no draw offer" in recv_until(a, lambda m: m["type"] == "error")["reason"]

    a.send_json({"type": "offer_draw"})
    assert recv_until(b, lambda m: m["type"] == "event" and m["kind"] == "draw_offer")["mark"] == "X"
    assert room_msg(b, lambda m: m["draw_offer"] == "X")["phase"] == "playing"
    a.send_json({"type": "answer_draw", "accept": True})  # can't accept your own offer
    assert "no draw offer" in recv_until(a, lambda m: m["type"] == "error")["reason"]

    b.send_json({"type": "answer_draw", "accept": False})
    assert recv_until(a, lambda m: m["type"] == "event" and m["kind"] == "draw_declined")["mark"] == "O"
    snap = room_msg(a, lambda m: m["draw_offer"] is None)
    assert snap["phase"] == "playing" and snap["game"]["game_id"] == first_game

    b.send_json({"type": "offer_draw"})
    room_msg(a, lambda m: m["draw_offer"] == "O")
    a.send_json({"type": "answer_draw", "accept": True})
    assert recv_until(b, lambda m: m["type"] == "event" and m["kind"] == "grid_drawn")["mark"] == "X"
    # Only the grid is drawn: a new one is dealt straight away and the series goes on
    snap = room_msg(b, lambda m: m["game"]["game_id"] != first_game)
    assert snap["phase"] == "playing" and snap["draw_offer"] is None
    assert snap["scores"] == {"X": 0, "O": 0} and snap["series"]["grid"] == 2
    assert snap["game"]["current_player"] == "O"  # starts still alternate
    assert manager.get_game(first_game) is None


def test_both_offering_a_draw_deals_a_new_grid(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    first_game = room.game_id
    a.send_json({"type": "offer_draw"})
    room_msg(b, lambda m: m["draw_offer"] == "X")
    b.send_json({"type": "offer_draw"})
    snap = room_msg(a, lambda m: m["game"]["game_id"] != first_game)
    assert snap["phase"] == "playing" and snap["series"]["grid"] == 2


def win_grid_for_x(rooms, manager, room, a, b):
    """Plays the room's current grid to a line of X on a known board."""
    game = manager.get_game(room.game_id)
    index = manager.indexes["nba"]
    game.row_criteria = [to_criterion(index.get(*k)) for k in ROWS]
    game.col_criteria = [to_criterion(index.get(*k)) for k in COLS]
    picks = [(a, 0, 0, "Alpha One"), (b, 1, 0, "Gamma Three"), (a, 0, 1, "Beta Two"),
             (b, 2, 0, "Nobody"), (a, 0, 2, "Delta Four")]
    if game.current_player == "O":
        picks.insert(0, (b, 2, 2, "Nobody"))  # a turnover hands X the ball
    for ws, row, col, name in picks:
        ws.send_json({"type": "pick", "row": row, "col": col, "name": name})
        recv_until(ws, lambda m: m["type"] == "room")
    return room_msg(b, lambda m: m["phase"] == "final")


def test_best_of_three_series(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    assert room.settings["best_of"] == 3

    final = win_grid_for_x(rooms, manager, room, a, b)
    assert final["scores"] == {"X": 1, "O": 0} and final["series"]["winner"] is None

    for ws in (a, b):
        ws.send_json({"type": "rematch"})
    room_msg(a, lambda m: m["phase"] == "playing" and m["series"]["grid"] == 2)
    final = win_grid_for_x(rooms, manager, room, a, b)
    assert final["scores"] == {"X": 2, "O": 0} and final["series"]["winner"] == "X"

    # Once the series is decided, the next rematch starts a new one from 0-0
    for ws in (a, b):
        ws.send_json({"type": "rematch"})
    snap = room_msg(a, lambda m: m["phase"] == "playing" and m["series"]["grid"] == 1)
    assert snap["scores"] == {"X": 0, "O": 0} and snap["series"]["winner"] is None


def test_best_of_one(online):
    client, rooms, manager = online
    res = client.post("/api/rooms", json={"league": "nba", "shot_clock": 0,
                                          "grid_style": "classic", "best_of": 1})
    assert rooms.get(res.json()["code"]).settings["best_of"] == 1
    assert client.post("/api/rooms", json={"best_of": 4}).status_code == 422


def test_spectators_cannot_skip_or_offer(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    s, _ = watch(client, code)
    for msg in ({"type": "skip"}, {"type": "offer_draw"}):
        s.send_json(msg)
        assert recv_until(s, lambda m: m["type"] == "error")["reason"] == "Spectators can watch but not play."


def test_room_games_refuse_the_same_device_routes(online):
    """The game id reaches spectators; it must not let anyone play or skip over HTTP."""
    from backend.api import build_router
    client, rooms, manager = online
    client.app.include_router(build_router(manager))
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    gid = room.game_id  # the same id every snapshot carries
    assert client.post("/api/shot-clock-violation", json={"game_id": gid}).status_code == 409
    assert client.post("/api/move", json={"game_id": gid, "row": 0, "col": 0,
                                          "player_name": "Alpha One"}).status_code == 409
    game = manager.get_game(gid)
    assert game.current_player == "X" and game.grid[0][0].claimed_by is None


def test_custom_room_deals_custom_grids(online):
    client, rooms, manager = online
    res = client.post("/api/rooms", json={"league": "nba", "shot_clock": 0, "grid_style": "custom",
                                          "categories": ["award"]})
    code = res.json()["code"]
    assert rooms.get(code).settings["categories"] == ["award"]
    a, _ = join(client, code, "Ann")
    b, _ = join(client, code, "Ben")
    a.send_json({"type": "ready"})
    b.send_json({"type": "ready"})
    game = room_msg(a, lambda m: m["phase"] == "playing")["game"]
    assert game["categories"] == ["award"]
    assert {c["type"] for c in game["row_criteria"] + game["col_criteria"]} <= {"team", "award"}


def test_online_pick_carries_the_chosen_player(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    game = manager.get_game(room.game_id)
    index = manager.indexes["nba"]
    game.row_criteria = [to_criterion(index.get(TEAM, t)) for t in ("Boston Celtics", "Miami Heat", "Chicago Bulls")]
    celtics_twin, heat_twin = sorted(index.catalog.find("Twin Name"), key=lambda p: p["teams"])
    # The Heat Twin, picked for a Boston box: the key is honoured, so it's a turnover
    a.send_json({"type": "pick", "row": 0, "col": 0, "name": "Twin Name", "key": heat_twin["key"]})
    event = recv_until(b, lambda m: m["type"] == "event" and m["kind"] in ("move", "turnover"))
    assert event["kind"] == "turnover" and "did not play for Boston Celtics" in event["text"]


def test_online_grid_ends_in_a_draw_when_no_line_is_left(online):
    client, rooms, manager = online
    code, room, a, b, _, _ = start_match(client, rooms, manager)
    game = manager.get_game(room.game_id)
    index = manager.indexes["nba"]
    game.row_criteria = [to_criterion(index.get(TEAM, t)) for t in ("Boston Celtics", "Chicago Bulls", "Miami Heat")]
    game.col_criteria = [to_criterion(index.get(TEAM, t)) for t in ("Los Angeles Lakers", "Boston Celtics", "Chicago Bulls")]
    for r, row in enumerate(("XOX", "XOO", "O..")):
        for c, mark in enumerate(row):
            if mark != ".":
                game.grid[r][c].claimed_by = mark
                game.grid[r][c].player_name = f"Filler {r}{c}"
    a.send_json({"type": "pick", "row": 2, "col": 1, "name": "Delta Four"})
    final = room_msg(b, lambda m: m["phase"] == "final")
    assert final["game"]["winner"] == "DRAW" and final["scores"] == {"X": 0, "O": 0}
    assert final["game"]["grid"][2][2]["claimed_by"] is None

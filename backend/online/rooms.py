"""Online rooms: two seats, one game at a time, a shot clock the server owns.

Every change to a room happens on the event loop under the room's lock, so a pick and an
expiring shot clock can never both apply to the same turn. After each change the whole
room is sent to everyone in it (see protocol.py for the message shapes).
"""

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from ..game.manager import GameManager
from ..game.rules import other_player
from .protocol import Focus, Join, Leave, Pick, Ready, Rematch

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ"  # no I, L or O: easy to read out loud
CODE_LENGTH = 4
DISCONNECT_GRACE = 120.0  # seconds a player may be gone mid-game before forfeiting
IDLE_TTL = 30 * 60        # empty rooms nobody touched for this long are removed


class RoomError(Exception):
    """A request the room refuses; the message goes back to the client."""


@dataclass(eq=False)
class Seat:
    mark: str
    name: str
    token: str
    sockets: Set = field(default_factory=set)
    ready: bool = False
    rematch: bool = False

    @property
    def connected(self) -> bool:
        return bool(self.sockets)


@dataclass(eq=False)
class Room:
    code: str
    settings: dict
    seats: Dict[str, Seat] = field(default_factory=dict)
    scores: Dict[str, int] = field(default_factory=lambda: {"X": 0, "O": 0})
    game_id: Optional[str] = None
    next_first: str = "X"                  # who starts the next game; alternates
    focus: Optional[dict] = None           # the box the player on the clock has open
    deadline: Optional[float] = None       # event-loop time the current turn runs out
    clock_task: Optional[asyncio.Task] = None
    forfeit_tasks: Dict[str, asyncio.Task] = field(default_factory=dict)
    last_activity: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RoomManager:
    def __init__(self, games: GameManager, disconnect_grace: float = DISCONNECT_GRACE,
                 idle_ttl: float = IDLE_TTL, game_max_age: Optional[float] = None):
        self.games = games
        self.disconnect_grace = disconnect_grace
        self.idle_ttl = idle_ttl
        self.game_max_age = game_max_age
        self.rooms: Dict[str, Room] = {}

    # ---------- Rooms ----------

    def create(self, settings: dict) -> Room:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.rooms:
                break
        room = Room(code=code, settings=dict(settings))
        self.rooms[code] = room
        return room

    def get(self, code: str) -> Optional[Room]:
        return self.rooms.get(code.upper())

    def game(self, room: Room):
        return self.games.get_game(room.game_id) if room.game_id else None

    def phase(self, room: Room) -> str:
        game = self.game(room)
        if game:
            return "playing" if game.status == "in_progress" else "final"
        return "lobby" if len(room.seats) == 2 else "waiting"

    def remove_idle(self) -> None:
        now = time.monotonic()
        for code, room in list(self.rooms.items()):
            if any(s.connected for s in room.seats.values()) or now - room.last_activity < self.idle_ttl:
                continue
            self._stop_clock(room)
            for task in room.forfeit_tasks.values():
                task.cancel()
            if room.game_id:
                self.games.discard(room.game_id)
            del self.rooms[code]

    async def cleanup_loop(self, interval: float = 60) -> None:
        while True:
            await asyncio.sleep(interval)
            self.remove_idle()
            if self.game_max_age:
                # Same-device games are never closed explicitly
                live = {room.game_id for room in self.rooms.values()}
                self.games.prune(self.game_max_age, keep=live)

    # ---------- Connections ----------

    async def connect(self, room: Room, ws, msg: Join) -> Seat:
        """Seats a new player, or puts a returning one (same token) back in their seat."""
        async with room.lock:
            seat = next((s for s in room.seats.values()
                         if msg.token and secrets.compare_digest(s.token, msg.token)), None)
            returning = seat is not None
            if not returning:
                free = [mark for mark in ("X", "O") if mark not in room.seats]
                if not free:
                    raise RoomError("This room is full.")
                name = msg.name.strip() or ("Player 1" if free[0] == "X" else "Player 2")
                seat = Seat(mark=free[0], name=name, token=secrets.token_urlsafe(16))
                room.seats[seat.mark] = seat
            seat.sockets.add(ws)
            task = room.forfeit_tasks.pop(seat.mark, None)
            if task:
                task.cancel()
            room.last_activity = time.monotonic()
            await self._send(ws, {"type": "welcome", "token": seat.token, "seat": seat.mark})
            await self._event(room, "reconnected" if returning else "joined", seat.mark,
                              f"{seat.name} {'is back' if returning else 'joined'}")
            await self._broadcast(room)
            return seat

    async def disconnect(self, room: Room, ws) -> None:
        async with room.lock:
            seat = next((s for s in room.seats.values() if ws in s.sockets), None)
            if not seat:
                return
            seat.sockets.discard(ws)
            if seat.connected:
                return  # another tab of the same player is still there
            game = self.game(room)
            if game and game.status == "in_progress":
                room.forfeit_tasks[seat.mark] = asyncio.get_running_loop().create_task(
                    self._forfeit_later(room, seat.mark))
            await self._event(room, "disconnected", seat.mark, f"{seat.name} lost connection")
            await self._broadcast(room)

    # ---------- Player actions ----------

    async def handle(self, room: Room, seat: Seat, msg) -> None:
        async with room.lock:
            room.last_activity = time.monotonic()
            if seat.mark not in room.seats:
                raise RoomError("You are no longer in this room.")
            if isinstance(msg, Ready):
                await self._on_ready(room, seat)
            elif isinstance(msg, Focus):
                await self._on_focus(room, seat, msg)
            elif isinstance(msg, Pick):
                await self._on_pick(room, seat, msg)
            elif isinstance(msg, Rematch):
                await self._on_rematch(room, seat)
            elif isinstance(msg, Leave):
                await self._on_leave(room, seat)

    async def _on_ready(self, room: Room, seat: Seat) -> None:
        if self.phase(room) == "playing":
            return
        if len(room.seats) < 2:
            raise RoomError("Waiting for an opponent to join.")
        seat.ready = True
        if all(s.ready for s in room.seats.values()):
            await self._start_game(room)
        await self._broadcast(room)

    async def _on_focus(self, room: Room, seat: Seat, msg: Focus) -> None:
        game = self.game(room)
        if not game or game.status != "in_progress" or game.current_player != seat.mark:
            return
        open_box = msg.row is not None and msg.col is not None and not game.grid[msg.row][msg.col].claimed_by
        room.focus = {"row": msg.row, "col": msg.col} if open_box else None
        await self._broadcast(room)

    async def _on_pick(self, room: Room, seat: Seat, msg: Pick) -> None:
        game = self.game(room)
        if not game or game.status != "in_progress":
            raise RoomError("No game is running.")
        if game.current_player != seat.mark:
            raise RoomError("It is not your turn.")
        result = self.games.make_move(game.game_id, msg.row, msg.col, msg.name)
        if not result.success and game.current_player == seat.mark:
            raise RoomError(result.message)  # a claimed box: no turnover, try another
        room.focus = None
        if result.success:
            await self._event(room, "move", seat.mark, result.message,
                              row=msg.row, col=msg.col, player=result.cell.player_name)
        else:
            await self._event(room, "turnover", seat.mark, result.message, player=msg.name)
        if result.game_over:
            await self._finish(room, result.winner)
        else:
            self._start_clock(room)
        await self._broadcast(room)

    async def _on_rematch(self, room: Room, seat: Seat) -> None:
        if self.phase(room) != "final":
            return
        seat.rematch = True
        if len(room.seats) == 2 and all(s.rematch for s in room.seats.values()):
            await self._start_game(room)
        await self._broadcast(room)

    async def _on_leave(self, room: Room, seat: Seat) -> None:
        game = self.game(room)
        if game and game.status == "in_progress":
            self.games.forfeit(game.game_id, seat.mark)
            await self._finish(room, other_player(seat.mark))
        del room.seats[seat.mark]
        for other in room.seats.values():
            other.ready = other.rematch = False
        await self._event(room, "left", seat.mark, f"{seat.name} left the room")
        await self._broadcast(room)

    # ---------- Games and the clock ----------

    async def _start_game(self, room: Room) -> None:
        if room.game_id:
            self.games.discard(room.game_id)
        s = room.settings
        game = self.games.create_game(
            league=s["league"], player1_name=room.seats["X"].name, player2_name=room.seats["O"].name,
            min_answers=s["min_answers"], shot_clock=s["shot_clock"], grid_style=s["grid_style"],
            first_player=room.next_first,
        )
        room.game_id = game.game_id
        room.next_first = other_player(room.next_first)
        room.focus = None
        for seat in room.seats.values():
            seat.ready = seat.rematch = False
        self._start_clock(room)
        await self._event(room, "tipoff", game.current_player, "Tip-off")

    async def _finish(self, room: Room, winner: str) -> None:
        self._stop_clock(room)
        room.focus = None
        if winner in room.scores:
            room.scores[winner] += 1
        await self._event(room, "final", winner, "Draw" if winner == "DRAW" else f"{winner} wins")

    def _start_clock(self, room: Room) -> None:
        self._stop_clock(room)
        length = room.settings.get("shot_clock") or 0
        if length <= 0:
            return
        loop = asyncio.get_running_loop()
        room.deadline = loop.time() + length
        room.clock_task = loop.create_task(self._expire(room, room.deadline))

    @staticmethod
    def _stop_clock(room: Room) -> None:
        if room.clock_task and room.clock_task is not asyncio.current_task():
            room.clock_task.cancel()
        room.clock_task = None
        room.deadline = None

    async def _expire(self, room: Room, deadline: float) -> None:
        await asyncio.sleep(max(0.0, deadline - asyncio.get_running_loop().time()))
        async with room.lock:
            game = self.game(room)
            if room.deadline != deadline or not game or game.status != "in_progress":
                return  # the turn already ended another way
            offender = game.current_player
            self.games.trigger_shot_clock_violation(game.game_id)
            room.focus = None
            self._start_clock(room)
            await self._event(room, "violation", offender, "Shot clock violation")
            await self._broadcast(room)

    async def _forfeit_later(self, room: Room, mark: str) -> None:
        await asyncio.sleep(self.disconnect_grace)
        async with room.lock:
            room.forfeit_tasks.pop(mark, None)
            seat = room.seats.get(mark)
            game = self.game(room)
            if not seat or seat.connected or not game or game.status != "in_progress":
                return
            self.games.forfeit(game.game_id, mark)
            await self._finish(room, other_player(mark))
            await self._event(room, "forfeit", mark, f"{seat.name} did not come back")
            await self._broadcast(room)

    # ---------- Messages ----------

    def snapshot(self, room: Room, you: str) -> dict:
        game = self.game(room)
        ms_left = None
        if room.deadline is not None and game and game.status == "in_progress":
            ms_left = max(0, int((room.deadline - asyncio.get_running_loop().time()) * 1000))
        return {
            "type": "room",
            "code": room.code,
            "you": you,
            "phase": self.phase(room),
            "settings": room.settings,
            "seats": {mark: {"name": s.name, "connected": s.connected, "ready": s.ready, "rematch": s.rematch}
                      for mark, s in room.seats.items()},
            "scores": room.scores,
            "game": game.model_dump(mode="json") if game else None,
            "turn_ms_left": ms_left,
            "focus": room.focus,
        }

    async def _broadcast(self, room: Room) -> None:
        for seat in room.seats.values():
            snapshot = self.snapshot(room, seat.mark)
            for ws in list(seat.sockets):
                await self._send(ws, snapshot)

    async def _event(self, room: Room, kind: str, mark: str, text: str, **extra) -> None:
        message = {"type": "event", "kind": kind, "mark": mark, "text": text, **extra}
        for seat in room.seats.values():
            for ws in list(seat.sockets):
                await self._send(ws, message)

    @staticmethod
    async def _send(ws, message: dict) -> None:
        try:
            await ws.send_json(message)
        except Exception:
            pass  # the socket is closing; its own handler cleans up

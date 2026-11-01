"""Online play routes: create or look up a room over HTTP, play it over a WebSocket."""

import asyncio
import json
from typing import Iterable
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ..models import CreateRoomRequest
from ..ratelimit import RateLimiter, client_key
from .protocol import Join, Leave, client_message
from .rooms import RoomError, RoomManager

JOIN_TIMEOUT = 10.0  # seconds a new socket has to say who it is


def build_online_router(rooms: RoomManager, limiter: RateLimiter, allowed_origins: Iterable[str] = ()) -> APIRouter:
    router = APIRouter()

    @router.post("/api/rooms")
    def create_room(req: CreateRoomRequest):
        return {"code": rooms.create(req.model_dump()).code}

    @router.get("/api/rooms/{code}")
    def room_info(code: str):
        room = rooms.get(code)
        if not room:
            raise HTTPException(status_code=404, detail="No room with that code")
        return {"code": room.code, "phase": rooms.phase(room), "players": len(room.seats),
                "settings": room.settings}

    @router.websocket("/ws/rooms/{code}")
    async def room_socket(ws: WebSocket, code: str):
        await ws.accept()
        client = client_key(ws.client.host if ws.client else None)
        if not _same_site(ws, allowed_origins):
            await _refuse(ws, "This page can't open a room.")
        elif not limiter.allow(client, "WS", ws.url.path):
            await _refuse(ws, "Too many joins, try again in a minute.")
        elif not limiter.open_socket(client):
            await _refuse(ws, "Too many connections from this address.")
        else:
            try:
                await _serve(ws, code, client)
            finally:
                limiter.close_socket(client)

    async def _serve(ws: WebSocket, code: str, client: str) -> None:
        room = rooms.get(code)
        if not room:
            await _refuse(ws, "No room with that code.")
            return
        joined = False
        try:
            frame = await asyncio.wait_for(_next_frame(ws), JOIN_TIMEOUT)
            first = client_message.validate_python(_parse(frame))
            if not isinstance(first, Join):
                raise RoomError("Join the room first.")
            seat = await rooms.connect(room, ws, first)  # None for a spectator
            joined = True
            while True:
                frame = await _next_frame(ws)
                try:
                    if not limiter.allow(client, "WS", "message"):
                        raise RoomError("Too many messages, slow down a little.")
                    msg = client_message.validate_python(_parse(frame))
                    if isinstance(msg, Join):
                        raise RoomError("Already in the room.")
                    await rooms.handle(room, seat, msg)
                except (ValidationError, RoomError) as e:
                    await ws.send_json({"type": "error", "reason": _reason(e)})
                    continue
                if isinstance(msg, Leave):
                    await ws.close()
                    break
        except WebSocketDisconnect:
            pass
        except asyncio.TimeoutError:
            await _refuse(ws, "Took too long to join.")
        except (ValidationError, RoomError) as e:
            await _refuse(ws, _reason(e))
        finally:
            if joined:
                await rooms.disconnect(room, ws)

    return router


def _same_site(ws: WebSocket, allowed_origins: Iterable[str]) -> bool:
    """Browsers always say which page opened a socket; only ours, or a listed site, may."""
    origin = ws.headers.get("origin")
    if not origin or "*" in allowed_origins or origin in allowed_origins:
        return True
    return urlsplit(origin).netloc == ws.headers.get("host")


async def _refuse(ws: WebSocket, reason: str) -> None:
    await ws.send_json({"type": "error", "reason": reason})
    await ws.close()


async def _next_frame(ws: WebSocket) -> dict:
    frame = await ws.receive()
    if frame["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(frame.get("code", 1000))
    return frame


def _parse(frame: dict):
    try:
        return json.loads(frame.get("text") or "")
    except (ValueError, RecursionError):
        raise RoomError("Malformed message.") from None


def _reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "Malformed message."
    return str(error)

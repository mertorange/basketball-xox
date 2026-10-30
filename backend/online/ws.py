"""Online play routes: create or look up a room over HTTP, play it over a WebSocket."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ..models import CreateRoomRequest
from ..ratelimit import RateLimiter
from .protocol import Join, Leave, client_message
from .rooms import RoomError, RoomManager


def build_online_router(rooms: RoomManager, limiter: RateLimiter) -> APIRouter:
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
        client = ws.client.host if ws.client else "unknown"
        if not limiter.allow(client, "WS", ws.url.path):
            await ws.send_json({"type": "error", "reason": "Too many joins, try again in a minute."})
            await ws.close()
            return
        room = rooms.get(code)
        if not room:
            await ws.send_json({"type": "error", "reason": "No room with that code."})
            await ws.close()
            return
        joined = False
        try:
            first = client_message.validate_python(await ws.receive_json())
            if not isinstance(first, Join):
                raise RoomError("Join the room first.")
            seat = await rooms.connect(room, ws, first)  # None for a spectator
            joined = True
            while True:
                data = await ws.receive_json()
                try:
                    if not limiter.allow(client, "WS", "message"):
                        raise RoomError("Too many messages, slow down a little.")
                    msg = client_message.validate_python(data)
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
        except (ValidationError, RoomError) as e:
            await ws.send_json({"type": "error", "reason": _reason(e)})
            await ws.close()
        finally:
            if joined:
                await rooms.disconnect(room, ws)

    return router


def _reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "Malformed message."
    return str(error)

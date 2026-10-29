"""WebSocket messages, client to server. Server messages are plain dicts built in rooms.py:

    {"type": "welcome", "token", "seat"}        after join: keep the token to reconnect
                                                (spectators get seat None and no token)
    {"type": "room", ...snapshot}               the full room state, after every change
    {"type": "event", "kind", "mark", "text"}   something happened: for sounds and the log
                                                (move, turnover, violation, skip, draw_offer,
                                                draw_declined, grid_drawn, final, ...)
    {"type": "error", "reason"}
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter


class Join(BaseModel):
    type: Literal["join"]
    name: str = Field("Player", max_length=24)
    token: Optional[str] = Field(None, max_length=64)
    role: Literal["player", "spectator"] = "player"


class Ready(BaseModel):
    type: Literal["ready"]


class Focus(BaseModel):
    """The player on the clock opened a box (or closed it: row and col None)."""
    type: Literal["focus"]
    row: Optional[int] = Field(None, ge=0, le=2)
    col: Optional[int] = Field(None, ge=0, le=2)


class Pick(BaseModel):
    type: Literal["pick"]
    row: int = Field(ge=0, le=2)
    col: int = Field(ge=0, le=2)
    name: str = Field(max_length=80)


class Skip(BaseModel):
    """The player on the clock passes the turn."""
    type: Literal["skip"]


class OfferDraw(BaseModel):
    """Ask the opponent to write this grid off as a draw (a new grid follows); the offer
    stands until answered."""
    type: Literal["offer_draw"]


class AnswerDraw(BaseModel):
    type: Literal["answer_draw"]
    accept: bool


class Rematch(BaseModel):
    """Ready for the next grid; once the series is decided, for a new series."""
    type: Literal["rematch"]


class Leave(BaseModel):
    type: Literal["leave"]


ClientMessage = Annotated[Union[Join, Ready, Focus, Pick, Skip, OfferDraw, AnswerDraw, Rematch, Leave],
                          Field(discriminator="type")]
client_message = TypeAdapter(ClientMessage)

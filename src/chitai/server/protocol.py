"""WebSocket protocol message definitions."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

# Outgoing messages (server → client)


class SessionItemInfo(BaseModel):
    """Information about an item in a session (queued, current, or completed)."""

    session_item_id: str
    text: str


class StatePayload(BaseModel):
    """Payload for state message."""

    session_id: str | None
    words: list[str]
    syllables: list[list[str]]
    current_word_index: int
    queue: list[SessionItemInfo]


class StateMessage(BaseModel):
    """State update message sent to clients."""

    type: Literal["state"]
    payload: StatePayload


# Incoming messages (client → server)


class StartSessionMessage(BaseModel):
    """Start a new reading session."""

    type: Literal["start_session"]


class EndSessionMessage(BaseModel):
    """End the current reading session."""

    type: Literal["end_session"]


class AddItemPayload(BaseModel):
    """Payload for add_item message."""

    text: str


class AddItemMessage(BaseModel):
    """Add a text item to the session."""

    type: Literal["add_item"]
    payload: AddItemPayload


class AdvanceWordPayload(BaseModel):
    """Payload for advance_word message."""

    delta: int = 1


class AdvanceWordMessage(BaseModel):
    """Advance to a different word in the current text."""

    type: Literal["advance_word"]
    payload: AdvanceWordPayload


# Discriminated union for incoming messages

IncomingMessage = Annotated[
    StartSessionMessage | EndSessionMessage | AddItemMessage | AdvanceWordMessage,
    Field(discriminator="type"),
]

# TypeAdapter for validating incoming messages
incoming_message_adapter = TypeAdapter(IncomingMessage)

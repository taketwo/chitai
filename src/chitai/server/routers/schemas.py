"""Pydantic schemas for REST API requests and responses."""

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

from chitai.db.models import Language  # noqa: TC001


class ItemResponse(BaseModel):
    """Response schema for a single item.

    Attributes
    ----------
    id : str
        Item UUID
    text : str
        The word, phrase, or sentence
    language : Language
        Language of the text (ru, de, en)
    created_at : datetime
        When the item was created
    usage_count : int
        Number of times this item was used in sessions
    last_used_at : datetime | None
        When this item was last displayed, None if never used

    """

    id: str
    text: str
    language: Language
    created_at: datetime
    usage_count: int = Field(ge=0)
    last_used_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemListResponse(BaseModel):
    """Response schema for listing items.

    Attributes
    ----------
    items : list[ItemResponse]
        List of items

    """

    items: list[ItemResponse]


class SessionResponse(BaseModel):
    """Response schema for a single session.

    Attributes
    ----------
    id : str
        Session UUID
    language : Language
        Language of the session (ru, de, en)
    started_at : datetime
        Session start time
    ended_at : datetime | None
        Session end time (None if still active)
    item_count : int
        Number of items displayed during this session

    """

    id: str
    language: Language
    started_at: datetime
    ended_at: datetime | None
    item_count: int = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    """Response schema for listing sessions.

    Attributes
    ----------
    sessions : list[SessionResponse]
        List of sessions

    """

    sessions: list[SessionResponse]


class SessionItemResponse(BaseModel):
    """Response schema for an item within a session.

    Attributes
    ----------
    id : str
        SessionItem UUID
    item_id : str
        Reference to Item
    text : str
        The item text
    displayed_at : datetime
        When item was shown
    completed_at : datetime | None
        When item was finished reading

    """

    id: str
    item_id: str
    text: str
    displayed_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(BaseModel):
    """Response schema for a single session with its items.

    Attributes
    ----------
    id : str
        Session UUID
    language : Language
        Language of the session (ru, de, en)
    started_at : datetime
        Session start time
    ended_at : datetime | None
        Session end time (None if still active)
    items : list[SessionItemResponse]
        Items displayed during this session, in order

    """

    id: str
    language: Language
    started_at: datetime
    ended_at: datetime | None
    items: list[SessionItemResponse]

    model_config = ConfigDict(from_attributes=True)

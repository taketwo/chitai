"""Pydantic schemas for REST API requests and responses."""

from datetime import datetime  # noqa: TC003
from typing import Literal

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
    illustration_count : int
        Number of illustrations linked to this item

    """

    id: str
    text: str
    language: Language
    created_at: datetime
    usage_count: int = Field(ge=0)
    last_used_at: datetime | None = None
    illustration_count: int = Field(ge=0, default=0)

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


class AutocompleteSuggestion(BaseModel):
    """Autocomplete suggestion for an item.

    Attributes
    ----------
    id : str
        Item UUID
    text : str
        The item text

    """

    id: str
    text: str

    model_config = ConfigDict(from_attributes=True)


class AutocompleteResponse(BaseModel):
    """Response schema for autocomplete suggestions.

    Attributes
    ----------
    suggestions : list[AutocompleteSuggestion]
        List of matching items

    """

    suggestions: list[AutocompleteSuggestion]


class IllustrationResponse(BaseModel):
    """Response schema for a single illustration.

    Attributes
    ----------
    id : str
        Illustration UUID
    source_url : str | None
        Original URL if imported from web
    width : int
        Pixel width
    height : int
        Pixel height
    file_size_bytes : int
        File size in bytes
    created_at : datetime
        When the illustration was imported
    item_count : int
        Number of items linked to this illustration

    """

    id: str
    source_url: str | None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    file_size_bytes: int = Field(ge=0)
    created_at: datetime
    item_count: int = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class IllustrationListResponse(BaseModel):
    """Response schema for listing illustrations.

    Attributes
    ----------
    illustrations : list[IllustrationResponse]
        List of illustrations
    total : int
        Total number of illustrations (for pagination)

    """

    illustrations: list[IllustrationResponse]
    total: int = Field(ge=0)


class ItemIllustrationResponse(BaseModel):
    """Response schema for an illustration linked to an item.

    Attributes
    ----------
    id : str
        Illustration UUID
    width : int
        Pixel width
    height : int
        Pixel height

    """

    id: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    model_config = ConfigDict(from_attributes=True)


class LogMessage(BaseModel):
    """Frontend log message.

    Attributes
    ----------
    level : str
        Log level (log, info, warn, error)
    message : str
        The log message
    args : list
        Additional arguments passed to console method

    """

    level: Literal["log", "info", "warn", "error"]
    message: str
    args: list = []

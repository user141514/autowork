from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageCreate(BaseModel):
    platform: str = "mock"
    room_id: str = "mock-room"
    sender_hash: str = "mock-user"
    sender_display_name: str | None = None
    timestamp: datetime | None = None
    message_type: str = "text"
    text: str
    attachments: list[Any] = Field(default_factory=list)
    raw_json: dict[str, Any] = Field(default_factory=dict)
    source_message_fingerprint: str | None = None


class ChatMessageImportRequest(BaseModel):
    messages: list[ChatMessageCreate]


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    room_id: str
    sender_hash: str
    sender_display_name: str | None
    timestamp: datetime
    message_type: str
    text: str
    attachments: list[Any]
    raw_json: dict[str, Any]
    source_message_fingerprint: str | None
    status: str

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SegmentFromMessagesRequest(BaseModel):
    message_ids: list[int]


class SegmentFromCommandRequest(BaseModel):
    context_window_size: int | None = None


class MessageSegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: str
    platform: str
    message_ids: list[int]
    text: str
    status: str
    created_at: datetime

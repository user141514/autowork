from pydantic import BaseModel, Field

from app.schemas.chat_message import ChatMessageRead


class WxautoPollRequest(BaseModel):
    room_id: str
    limit: int | None = None


class WxautoSendRequest(BaseModel):
    room_id: str
    text: str


class WxautoPollResponse(BaseModel):
    room_id: str
    messages: list[ChatMessageRead]
    status: str = "ok"


class ManualExportImportRequest(BaseModel):
    file_path: str
    room_id: str = "manual-export"
    platform: str = "manual_export"
    encoding: str = "utf-8"
    sender_display_name: str | None = None


class LocalDatabaseImportRequest(BaseModel):
    path: str
    room_id: str | None = None
    metadata: dict = Field(default_factory=dict)

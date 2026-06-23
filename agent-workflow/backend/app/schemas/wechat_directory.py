from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ConversationKind = Literal["chatroom", "contact", "filehelper", "official", "unknown", "all"]


class WeChatConversationRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: ConversationKind
    display_name: str = Field(alias="displayName")
    raw_name: str = Field(alias="rawName")
    remark: str | None = None
    nickname: str | None = Field(default=None, alias="nickName")
    alias: str | None = None
    session_name: str | None = Field(default=None, alias="sessionName")
    message_count: int = Field(alias="messageCount")
    latest_time: datetime | None = Field(default=None, alias="latestTime")
    last_preview: str | None = Field(default=None, alias="lastPreview")
    source: str


class WeChatDirectoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversations: list[WeChatConversationRead]
    count: int
    limit: int
    query: str | None = None
    kind: ConversationKind


class WeChatMessagePageItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    conversation_display_name: str = Field(alias="conversationDisplayName")
    sender_id: str = Field(alias="senderId")
    sender_display_name: str = Field(alias="senderDisplayName")
    timestamp: datetime
    create_time: int = Field(alias="createTime")
    local_id: int | None = Field(default=None, alias="localId")
    msg_svr_id: str | None = Field(default=None, alias="msgSvrId")
    message_type: str = Field(alias="messageType")
    raw_type: int | None = Field(default=None, alias="rawType")
    text: str
    original_text: str = Field(alias="originalText")
    source_db: str = Field(alias="sourceDb")


class WeChatMessageCursor(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    before_ts: int | None = Field(default=None, alias="beforeTs")
    before_local_id: int | None = Field(default=None, alias="beforeLocalId")


class WeChatMessagePageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[WeChatMessagePageItem]
    count: int
    limit: int
    has_more: bool = Field(alias="hasMore")
    next_cursor: WeChatMessageCursor | None = Field(default=None, alias="nextCursor")

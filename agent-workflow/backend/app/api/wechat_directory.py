from pathlib import Path

from fastapi import APIRouter

from app.schemas.wechat_directory import ConversationKind, WeChatDirectoryResponse, WeChatMessagePageResponse
from app.services.wechat_directory import DEFAULT_MESSAGE_PAGE_LIMIT, MAX_CONVERSATION_LIMIT, MAX_MESSAGE_PAGE_LIMIT, WeChatDirectoryService


router = APIRouter(prefix="/wechat-directory", tags=["wechat-directory"])
DEFAULT_DECRYPTED_WECHAT_DIR = Path(__file__).resolve().parents[4] / "external_tools" / "decrypted_wechat"


@router.get("/conversations", response_model=WeChatDirectoryResponse, response_model_by_alias=True)
def list_conversations(kind: ConversationKind = "all", query: str | None = None, limit: int = 100):
    safe_limit = max(1, min(limit, MAX_CONVERSATION_LIMIT))
    conversations = WeChatDirectoryService(DEFAULT_DECRYPTED_WECHAT_DIR).list_conversations(
        kind=kind,
        query=query,
        limit=safe_limit,
    )
    return WeChatDirectoryResponse(
        conversations=conversations,
        count=len(conversations),
        limit=safe_limit,
        query=query,
        kind=kind,
    )


@router.get("/messages", response_model=WeChatMessagePageResponse, response_model_by_alias=True)
def page_wechat_messages(
    conversation_id: str,
    before_ts: int | None = None,
    before_local_id: int | None = None,
    limit: int = DEFAULT_MESSAGE_PAGE_LIMIT,
):
    safe_limit = max(1, min(limit, MAX_MESSAGE_PAGE_LIMIT))
    return WeChatDirectoryService(DEFAULT_DECRYPTED_WECHAT_DIR).page_messages(
        conversation_id=conversation_id,
        before_ts=before_ts,
        before_local_id=before_local_id,
        limit=safe_limit,
    )

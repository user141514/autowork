from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.adapters.chat.local_database_import_adapter_stub import LocalDatabaseImportAdapterStub
from app.adapters.chat.manual_export_adapter import ManualExportAdapter
from app.adapters.chat.wxauto_adapter import PersonalWeChatAdapter
from app.database import get_db
from app.schemas.chat_message import ChatMessageRead
from app.schemas.wechat import (
    LocalDatabaseImportRequest,
    ManualExportImportRequest,
    WxautoPollRequest,
    WxautoPollResponse,
    WxautoSendRequest,
)
from app.services.message_store import MessageStore
from app.config import get_settings


router = APIRouter(prefix="/wechat", tags=["wechat"])


@router.get("/health")
def wechat_health():
    return PersonalWeChatAdapter().health_check()


@router.post("/poll-room", response_model=WxautoPollResponse)
def poll_room(request: WxautoPollRequest, db: Session = Depends(get_db)):
    limit = request.limit or get_settings().wechat_read_limit
    messages = PersonalWeChatAdapter().fetch_recent(request.room_id, limit)
    saved = MessageStore(db).import_messages(messages)
    return WxautoPollResponse(
        room_id=request.room_id,
        messages=[ChatMessageRead.model_validate(message) for message in saved],
    )


@router.post("/poll-once", response_model=list[WxautoPollResponse])
def poll_once(db: Session = Depends(get_db)):
    responses: list[WxautoPollResponse] = []
    for room_id in get_settings().wechat_whitelist_rooms:
        messages = PersonalWeChatAdapter().fetch_recent(room_id, get_settings().wechat_read_limit)
        saved = MessageStore(db).import_messages(messages)
        responses.append(
            WxautoPollResponse(
                room_id=room_id,
                messages=[ChatMessageRead.model_validate(message) for message in saved],
            )
        )
    return responses


@router.post("/wxauto/poll", response_model=WxautoPollResponse)
def poll_wxauto(request: WxautoPollRequest, db: Session = Depends(get_db)):
    return poll_room(request, db)


@router.post("/wxauto/send")
def send_wxauto(request: WxautoSendRequest):
    PersonalWeChatAdapter().send_message(request.room_id, request.text)
    return {"status": "sent", "room_id": request.room_id}


@router.post("/manual-export/import", response_model=list[ChatMessageRead])
def import_manual_export(request: ManualExportImportRequest, db: Session = Depends(get_db)):
    messages = ManualExportAdapter().import_file(
        file_path=request.file_path,
        room_id=request.room_id,
        platform=request.platform,
        encoding=request.encoding,
        sender_display_name=request.sender_display_name,
    )
    return MessageStore(db).import_messages(messages)


@router.post("/local-db/import")
def import_local_database(request: LocalDatabaseImportRequest):
    LocalDatabaseImportAdapterStub().import_database(request.path, request.room_id)
    return {"status": "not_implemented"}

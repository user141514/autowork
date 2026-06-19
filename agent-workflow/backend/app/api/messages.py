from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat_message import ChatMessageImportRequest, ChatMessageRead
from app.services.agent_input_builder import build_agent_input
from app.services.message_store import MessageStore


router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/import", response_model=list[ChatMessageRead])
def import_messages(request: ChatMessageImportRequest, db: Session = Depends(get_db)):
    return MessageStore(db).import_messages(request.messages)


@router.get("", response_model=list[ChatMessageRead])
def list_messages(
    room_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int | None = None,
    order: str = "asc",
    db: Session = Depends(get_db),
):
    return MessageStore(db).list_messages(
        room_id=room_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        order=order,
    )


@router.get("/latest", response_model=list[ChatMessageRead])
def latest_messages(
    room_id: str | None = None,
    since_cursor: int = 0,
    limit: int | None = None,
    db: Session = Depends(get_db),
):
    return MessageStore(db).list_messages_since_cursor(room_id=room_id, since_cursor=since_cursor, limit=limit)


@router.get("/agent-input", response_class=PlainTextResponse)
def agent_input(
    room_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int | None = None,
    order: str = "asc",
    db: Session = Depends(get_db),
):
    messages = MessageStore(db).list_messages(
        room_id=room_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        order=order,
    )
    return build_agent_input(messages)

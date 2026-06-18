from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat_message import ChatMessageImportRequest, ChatMessageRead
from app.services.message_store import MessageStore


router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/import", response_model=list[ChatMessageRead])
def import_messages(request: ChatMessageImportRequest, db: Session = Depends(get_db)):
    return MessageStore(db).import_messages(request.messages)


@router.get("", response_model=list[ChatMessageRead])
def list_messages(db: Session = Depends(get_db)):
    return MessageStore(db).list_messages()

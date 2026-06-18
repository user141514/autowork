from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.bot_command import BotCommandProcessRequest, BotCommandRead
from app.services.bot_command_service import BotCommandService


router = APIRouter(prefix="/bot", tags=["bot"])


@router.post("/command", response_model=BotCommandRead)
def process_command(request: BotCommandProcessRequest, db: Session = Depends(get_db)):
    return BotCommandService(db).process_message(request.message_id)


@router.post("/process-new-messages", response_model=list[BotCommandRead])
def process_new_messages(db: Session = Depends(get_db)):
    return BotCommandService(db).process_new_messages()


@router.get("/commands", response_model=list[BotCommandRead])
def list_commands(db: Session = Depends(get_db)):
    return BotCommandService(db).list_logs()

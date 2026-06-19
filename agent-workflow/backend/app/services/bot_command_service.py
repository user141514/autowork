import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.bot_command_log import BotCommandLog
from app.models.chat_message import ChatMessage
from app.models.enums import WorkflowStatus
from app.services.errors import InvalidStateError, NotFoundError
from app.services.message_store import MessageStore


class BotCommandType:
    RECORD_TASK = "record_task"
    GENERATE_WORKDOC = "generate_workdoc"
    STATUS = "status"
    CONFIRM_EXECUTION = "confirm_execution"
    REPORT = "report"
    UNKNOWN = "unknown"


class BotCommandService:
    def __init__(self, db: Session):
        self.db = db

    def process_message(self, message_id: int) -> BotCommandLog:
        message = self.db.get(ChatMessage, message_id)
        if message is None:
            raise NotFoundError(f"message not found: {message_id}")
        existing = self.db.scalars(select(BotCommandLog).where(BotCommandLog.message_id == message_id)).first()
        if existing is not None:
            return existing
        parsed = parse_bot_command(message.text)
        if parsed is None:
            raise InvalidStateError("ordinary message ignored; no bot command log created")
        command_type, command_text, workdoc_id, error_code = parsed
        log = BotCommandLog(
            message_id=message.id,
            room_id=message.room_id,
            command_type=command_type,
            command_text=command_text,
            target_workdoc_id=workdoc_id,
            status=WorkflowStatus.BOT_COMMAND_LOGGED.value,
            error_code=error_code,
            metadata_json={"source": message.platform},
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def process_new_messages(self, message_ids: list[int] | None = None) -> list[BotCommandLog]:
        logs: list[BotCommandLog] = []
        messages = MessageStore(self.db).list_unprocessed_command_messages()
        if message_ids is not None:
            allowed_ids = set(message_ids)
            messages = [message for message in messages if message.id in allowed_ids]
        for message in messages:
            try:
                logs.append(self.process_message(message.id))
            except InvalidStateError:
                continue
        return logs

    def list_logs(self) -> list[BotCommandLog]:
        return list(self.db.scalars(select(BotCommandLog).order_by(BotCommandLog.id.asc())))


def parse_bot_command(text: str) -> tuple[str, str, int | None, str | None] | None:
    mention = get_settings().workbot_mention
    if mention not in text:
        return None
    command_text = text.split(mention, 1)[1].strip()
    workdoc_id = _extract_workdoc_id(command_text)
    if "记录为任务" in command_text:
        return BotCommandType.RECORD_TASK, command_text, workdoc_id, None
    if "生成WorkDoc" in command_text or "生成 WorkDoc" in command_text:
        return BotCommandType.GENERATE_WORKDOC, command_text, workdoc_id, None
    if command_text.startswith("状态"):
        return BotCommandType.STATUS, command_text, workdoc_id, None if workdoc_id else "WORKDOC_ID_MISSING"
    if command_text.startswith("确认执行"):
        return BotCommandType.CONFIRM_EXECUTION, command_text, workdoc_id, None if workdoc_id else "WORKDOC_ID_MISSING"
    if command_text.startswith("报告"):
        return BotCommandType.REPORT, command_text, workdoc_id, None if workdoc_id else "WORKDOC_ID_MISSING"
    return BotCommandType.UNKNOWN, command_text, workdoc_id, "UNKNOWN_COMMAND"


def _extract_workdoc_id(text: str) -> int | None:
    match = re.search(r"WD-(\d+)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None

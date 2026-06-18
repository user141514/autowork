from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message_segment import MessageSegment
from app.models.chat_message import ChatMessage
from app.models.bot_command_log import BotCommandLog
from app.schemas.segment import SegmentFromMessagesRequest
from app.services.errors import InvalidStateError, NotFoundError
from app.config import get_settings
from app.services.message_store import MessageStore


class SegmentService:
    def __init__(self, db: Session):
        self.db = db

    def create_from_messages(self, request: SegmentFromMessagesRequest) -> MessageSegment:
        messages = MessageStore(self.db).get_messages_by_ids(request.message_ids)
        if len(messages) != len(request.message_ids):
            found_ids = {message.id for message in messages}
            missing = [message_id for message_id in request.message_ids if message_id not in found_ids]
            raise NotFoundError(f"messages not found: {missing}")
        first = messages[0]
        segment = MessageSegment(
            room_id=first.room_id,
            platform=first.platform,
            message_ids=[message.id for message in messages],
            text="\n".join(message.text for message in messages),
        )
        self.db.add(segment)
        self.db.commit()
        self.db.refresh(segment)
        return segment

    def create_from_command(self, message_id: int, context_window_size: int | None = None) -> MessageSegment:
        message = self.db.get(ChatMessage, message_id)
        if message is None:
            raise NotFoundError(f"message not found: {message_id}")
        command = self.db.scalars(select(BotCommandLog).where(BotCommandLog.message_id == message_id)).first()
        if command is None:
            raise InvalidStateError("BotCommandLog is required before creating a segment")
        if command.command_type not in {"record_task", "generate_workdoc"}:
            raise InvalidStateError(f"command cannot create segment: {command.command_type}")

        window = context_window_size or get_settings().wechat_context_window_size
        rows = list(
            self.db.scalars(
                select(ChatMessage)
                .where(ChatMessage.room_id == message.room_id)
                .where(ChatMessage.id <= message.id)
                .order_by(ChatMessage.id.desc())
                .limit(max(window, 1))
            )
        )
        messages = list(reversed(rows))
        if not messages:
            raise InvalidStateError("SEGMENT_CONTEXT_EMPTY")
        segment = MessageSegment(
            room_id=message.room_id,
            platform=message.platform,
            message_ids=[row.id for row in messages],
            text="\n".join(row.text for row in messages),
        )
        self.db.add(segment)
        self.db.commit()
        self.db.refresh(segment)
        return segment

    def list_segments(self) -> list[MessageSegment]:
        return list(self.db.scalars(select(MessageSegment).order_by(MessageSegment.id.asc())))

    def get_segment(self, segment_id: int) -> MessageSegment:
        segment = self.db.get(MessageSegment, segment_id)
        if segment is None:
            raise NotFoundError(f"segment not found: {segment_id}")
        return segment

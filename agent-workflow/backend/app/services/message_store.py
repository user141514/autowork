import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate


class MessageStore:
    def __init__(self, db: Session):
        self.db = db

    def import_messages(self, messages: list[ChatMessageCreate]) -> list[ChatMessage]:
        saved: list[ChatMessage] = []
        for message in messages:
            fingerprint = message.source_message_fingerprint or source_message_fingerprint(message)
            existing = self.db.scalars(
                select(ChatMessage).where(ChatMessage.source_message_fingerprint == fingerprint)
            ).first()
            if existing is not None:
                saved.append(existing)
                continue
            db_message = ChatMessage(
                platform=message.platform,
                room_id=message.room_id,
                sender_hash=message.sender_hash,
                sender_display_name=message.sender_display_name,
                timestamp=message.timestamp or datetime.now(timezone.utc),
                message_type=message.message_type,
                text=message.text,
                attachments=message.attachments,
                raw_json=message.raw_json or message.model_dump(mode="json"),
                source_message_fingerprint=fingerprint,
            )
            self.db.add(db_message)
            saved.append(db_message)
        self.db.commit()
        for message in saved:
            self.db.refresh(message)
        return saved

    def list_messages(self) -> list[ChatMessage]:
        return list(self.db.scalars(select(ChatMessage).order_by(ChatMessage.id.asc())))

    def get_messages_by_ids(self, message_ids: list[int]) -> list[ChatMessage]:
        if not message_ids:
            return []
        rows = list(self.db.scalars(select(ChatMessage).where(ChatMessage.id.in_(message_ids))))
        by_id = {row.id: row for row in rows}
        return [by_id[message_id] for message_id in message_ids if message_id in by_id]

    def list_unprocessed_command_messages(self) -> list[ChatMessage]:
        from app.models.bot_command_log import BotCommandLog

        mention = get_settings().workbot_mention
        logged_message_ids = select(BotCommandLog.message_id)
        return list(
            self.db.scalars(
                select(ChatMessage)
                .where(ChatMessage.text.contains(mention))
                .where(ChatMessage.id.not_in(logged_message_ids))
                .order_by(ChatMessage.id.asc())
            )
        )


def source_message_fingerprint(message: ChatMessageCreate) -> str:
    timestamp = message.timestamp or datetime.now(timezone.utc)
    bucket = timestamp.replace(second=0, microsecond=0).isoformat()
    raw = "|".join(
        [
            message.platform,
            message.room_id,
            message.sender_hash,
            bucket,
            message.message_type,
            message.text.strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate


class MessageStore:
    def __init__(self, db: Session):
        self.db = db

    def import_messages(self, messages: list[ChatMessageCreate]) -> list[ChatMessage]:
        saved: list[ChatMessage] = []
        for message in messages:
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

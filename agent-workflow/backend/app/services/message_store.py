import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate


class MessageFingerprintPolicy:
    def fingerprint_for(self, message: ChatMessageCreate) -> str:
        return message.source_message_fingerprint or source_message_fingerprint(message)


class ChatMessageFactory:
    def build(self, message: ChatMessageCreate, fingerprint: str) -> ChatMessage:
        return ChatMessage(
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


@dataclass(frozen=True)
class MessageImportResult:
    messages: list[ChatMessage]
    inserted_count: int
    reused_count: int


class MessageBatchIdentityMap:
    def __init__(self):
        self._messages: dict[str, ChatMessage] = {}

    def get(self, key: str) -> ChatMessage | None:
        return self._messages.get(key)

    def remember(self, key: str, message: ChatMessage) -> None:
        self._messages[key] = message


class MessageStore:
    def __init__(self, db: Session, fingerprint_policy: MessageFingerprintPolicy | None = None, message_factory: ChatMessageFactory | None = None):
        self.db = db
        self.fingerprint_policy = fingerprint_policy or MessageFingerprintPolicy()
        self.message_factory = message_factory or ChatMessageFactory()

    def find_by_fingerprint(self, fingerprint: str) -> ChatMessage | None:
        return self.db.scalars(select(ChatMessage).where(ChatMessage.source_message_fingerprint == fingerprint)).first()

    def import_messages(self, messages: list[ChatMessageCreate]) -> list[ChatMessage]:
        saved: list[ChatMessage] = []
        seen_in_batch = MessageBatchIdentityMap()
        for message in messages:
            fingerprint = self.fingerprint_policy.fingerprint_for(message)
            batch_message = seen_in_batch.get(fingerprint)
            if batch_message is not None:
                saved.append(batch_message)
                continue
            existing = self.find_by_fingerprint(fingerprint)
            if existing is not None:
                saved.append(existing)
                seen_in_batch.remember(fingerprint, existing)
                continue
            db_message = self.message_factory.build(message, fingerprint)
            self.db.add(db_message)
            saved.append(db_message)
            seen_in_batch.remember(fingerprint, db_message)
        self.save_changes()
        self.refresh_saved(saved)
        return saved

    def import_messages_with_result(self, messages: list[ChatMessageCreate]) -> MessageImportResult:
        fingerprints = [self.fingerprint_policy.fingerprint_for(message) for message in messages]
        existing = {fingerprint for fingerprint in set(fingerprints) if self.find_by_fingerprint(fingerprint) is not None}
        saved = self.import_messages(messages)
        inserted_count = len(set(fingerprints) - existing)
        return MessageImportResult(messages=saved, inserted_count=inserted_count, reused_count=max(0, len(messages) - inserted_count))

    def save_changes(self) -> None:
        self.db.commit()

    def refresh_saved(self, saved: list[ChatMessage]) -> None:
        for message in saved:
            self.db.refresh(message)

    def list_messages(
        self,
        room_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        order: str = "asc",
    ) -> list[ChatMessage]:
        stmt = select(ChatMessage)
        if room_id is not None:
            stmt = stmt.where(ChatMessage.room_id == room_id)
        if start_time is not None:
            stmt = stmt.where(ChatMessage.timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(ChatMessage.timestamp <= end_time)
        stmt = stmt.order_by(ChatMessage.timestamp.desc() if order == "desc" else ChatMessage.timestamp.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def list_messages_since_cursor(self, room_id: str | None, since_cursor: int, limit: int | None = None) -> list[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.id > since_cursor)
        if room_id is not None:
            stmt = stmt.where(ChatMessage.room_id == room_id)
        stmt = stmt.order_by(ChatMessage.id.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def list_messages_page(
        self,
        room_id: str,
        before_id: int | None = None,
        after_id: int | None = None,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.room_id == room_id)
        if after_id is not None:
            stmt = stmt.where(ChatMessage.id > after_id).order_by(ChatMessage.id.asc())
        else:
            if before_id is not None:
                stmt = stmt.where(ChatMessage.id < before_id)
            stmt = stmt.order_by(ChatMessage.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

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
    timestamp_value = message.timestamp.isoformat() if message.timestamp is not None else "no_timestamp"
    raw = "|".join(
        [
            message.platform,
            message.room_id,
            message.sender_hash,
            timestamp_value,
            message.message_type,
            message.text.strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

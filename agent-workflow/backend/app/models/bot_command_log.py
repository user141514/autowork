from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import WorkflowStatus


class BotCommandLog(Base):
    __tablename__ = "bot_command_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id"), index=True)
    room_id: Mapped[str] = mapped_column(String(255), index=True)
    command_type: Mapped[str] = mapped_column(String(64), index=True)
    command_text: Mapped[str] = mapped_column(Text, default="")
    target_workdoc_id: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(64), default=WorkflowStatus.BOT_COMMAND_LOGGED.value, index=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

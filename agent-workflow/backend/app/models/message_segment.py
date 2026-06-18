from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import WorkflowStatus


class MessageSegment(Base):
    __tablename__ = "message_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    room_id: Mapped[str] = mapped_column(String(255), index=True)
    platform: Mapped[str] = mapped_column(String(64), default="mock", index=True)
    message_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default=WorkflowStatus.SEGMENT_CREATED.value, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

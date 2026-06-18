from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    room_id: Mapped[str] = mapped_column(String(255), index=True)
    adapter_type: Mapped[str] = mapped_column(String(64), default="mock")
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[int] = mapped_column(index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default="created", index=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

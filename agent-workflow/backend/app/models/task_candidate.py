from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import WorkflowStatus


class TaskCandidate(Base):
    __tablename__ = "task_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("message_segments.id"), index=True)
    room_id: Mapped[str] = mapped_column(String(255), index=True)
    command_text: Mapped[str] = mapped_column(Text, default="")
    evidence_message_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    repo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    workdoc_id: Mapped[int | None] = mapped_column(ForeignKey("workdocs.id"), nullable=True, index=True)
    confidence: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[str] = mapped_column(String(64), default=WorkflowStatus.TASK_CANDIDATE_CREATED.value, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

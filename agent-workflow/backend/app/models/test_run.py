from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workdoc_id: Mapped[int] = mapped_column(ForeignKey("workdocs.id"), index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    command: Mapped[str] = mapped_column(Text, default="")
    stdout_log: Mapped[str] = mapped_column(Text, default="")
    stderr_log: Mapped[str] = mapped_column(Text, default="")
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

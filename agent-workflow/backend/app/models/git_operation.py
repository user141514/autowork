from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import WorkflowStatus


class GitOperation(Base):
    __tablename__ = "git_operations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workdoc_id: Mapped[int] = mapped_column(ForeignKey("workdocs.id"), index=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    changed_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    diff_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    diff_summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default=WorkflowStatus.PATCH_CREATED.value, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

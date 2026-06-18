from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import AgentType, WorkflowStatus


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workdoc_id: Mapped[int] = mapped_column(ForeignKey("workdocs.id"), index=True)
    agent_type: Mapped[str] = mapped_column(String(64), default=AgentType.MOCK.value)
    repo_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(64), default=WorkflowStatus.AGENT_RUN_CREATED.value, index=True)
    command: Mapped[str] = mapped_column(Text, default="")
    stdout_log: Mapped[str] = mapped_column(Text, default="")
    stderr_log: Mapped[str] = mapped_column(Text, default="")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    diff_summary: Mapped[str] = mapped_column(Text, default="")
    changed_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[str] = mapped_column(Text, default="")

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import RiskLevel, WorkflowStatus


class WorkDoc(Base):
    __tablename__ = "workdocs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    repo_name: Mapped[str] = mapped_column(String(255), default="demo-repo")
    repo_path: Mapped[str] = mapped_column(String(1024), default=".")
    branch_base: Mapped[str] = mapped_column(String(255), default="main")
    problem_summary: Mapped[str] = mapped_column(Text)
    observed_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[list[str]] = mapped_column(JSON, default=list)
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_message_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    uncertainties: Mapped[list[str]] = mapped_column(JSON, default=list)
    execution: Mapped[dict] = mapped_column(JSON, default=dict)
    test: Mapped[dict] = mapped_column(JSON, default=dict)
    agent: Mapped[dict] = mapped_column(JSON, default=dict)
    git: Mapped[dict] = mapped_column(JSON, default=dict)
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(32), default=RiskLevel.LOW.value)
    status: Mapped[str] = mapped_column(String(64), default=WorkflowStatus.WORKDOC_DRAFTED.value, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

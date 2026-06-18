from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GitCommitRequest(BaseModel):
    dry_run: bool | None = None
    branch_name: str | None = None
    commit_message: str | None = None


class GitOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workdoc_id: int
    agent_run_id: int
    branch_name: str | None
    commit_hash: str | None
    pr_url: str | None
    changed_files: list[str]
    diff_stats: dict
    diff_summary: str
    status: str
    created_at: datetime


class GitDiffRead(BaseModel):
    agent_run_id: int
    changed_files: list[str]
    diff_stats: dict
    diff_summary: str

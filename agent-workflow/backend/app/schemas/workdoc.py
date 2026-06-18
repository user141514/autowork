from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionConfig(BaseModel):
    allowed_paths: list[str] = Field(default_factory=lambda: ["**/*"])
    forbidden_paths: list[str] = Field(default_factory=lambda: [".env", "secrets.*", "*.pem", "*.key"])


class TestConfig(BaseModel):
    commands: list[str] = Field(default_factory=list)
    required: bool = False


class AgentConfig(BaseModel):
    preferred_runner: str = "mock"
    timeout_seconds: int = 120
    max_diff_lines: int = 1000


class GitConfig(BaseModel):
    branch_prefix: str = "agent-workflow"
    commit_message_template: str = "WorkDoc {workdoc_id}: {title}"
    allow_push: bool = False
    allow_pr: bool = False


class ReviewConfig(BaseModel):
    require_human_approval: bool = True
    risk_level: Literal["low", "medium", "high"] = "low"


class WorkDocFromMessagesRequest(BaseModel):
    message_ids: list[int]
    repo_name: str = "demo-repo"
    repo_path: str = "."
    branch_base: str = "main"
    execution: ExecutionConfig | None = None
    test: TestConfig | None = None
    agent: AgentConfig | None = None
    git: GitConfig | None = None
    review: ReviewConfig | None = None


class WorkDocFromTaskCandidateRequest(BaseModel):
    task_candidate_id: int
    repo_name: str = "demo-repo"
    repo_path: str = "."
    branch_base: str = "main"
    execution: ExecutionConfig | None = None
    test: TestConfig | None = None
    agent: AgentConfig | None = None
    git: GitConfig | None = None
    review: ReviewConfig | None = None


class WorkDocUpdateRequest(BaseModel):
    title: str | None = None
    problem_summary: str | None = None
    observed_behavior: str | None = None
    expected_behavior: str | None = None
    constraints: list[str] | None = None
    acceptance_criteria: list[str] | None = None
    evidence_message_ids: list[int] | None = None
    uncertainties: list[str] | None = None
    execution: ExecutionConfig | None = None
    test: TestConfig | None = None
    agent: AgentConfig | None = None
    git: GitConfig | None = None
    review: ReviewConfig | None = None


class WorkDocRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    repo_name: str
    repo_path: str
    branch_base: str
    problem_summary: str
    observed_behavior: str | None
    expected_behavior: str | None
    constraints: list[str]
    acceptance_criteria: list[str]
    evidence_message_ids: list[int]
    uncertainties: list[str]
    execution: dict
    test: dict
    agent: dict
    git: dict
    review: dict
    risk_level: str
    status: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None


class WorkDocValidationResult(BaseModel):
    workdoc: WorkDocRead
    valid: bool
    reasons: list[str] = Field(default_factory=list)

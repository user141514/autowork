from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.demand_radar import CandidateRequirement


ReviewDecision = Literal["confirm", "reject", "merge", "expire"]
WorkDocDraftStatus = Literal["draft", "approved_for_agent", "rejected"]
PromotedRequirementType = Literal["bugfix", "feature", "config", "data", "doc", "process"]


class ConfirmedRequirementFields(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_or_repo: str = Field(alias="projectOrRepo")
    working_dir: str | None = Field(default=None, alias="workingDir")
    branch: str | None = None
    module: str | None = None
    page: str | None = None
    target_object: str | None = Field(default=None, alias="targetObject")
    actual_behavior: str | None = Field(default=None, alias="actualBehavior")
    expected_behavior: str | None = Field(default=None, alias="expectedBehavior")
    desired_behavior: str | None = Field(default=None, alias="desiredBehavior")
    scope: str
    constraints: list[str]
    acceptance_criteria: list[str] = Field(alias="acceptanceCriteria")
    out_of_scope: list[str] = Field(default_factory=list, alias="outOfScope")
    human_notes: str | None = Field(default=None, alias="humanNotes")
    allow_agent: bool = Field(alias="allowAgent")


class HumanReviewDecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str = Field(alias="candidateId")
    decision: ReviewDecision
    reviewer: str
    reviewed_at: datetime = Field(alias="reviewedAt")
    reason: str | None = None
    merge_target_candidate_id: str | None = Field(default=None, alias="mergeTargetCandidateId")
    human_fields: ConfirmedRequirementFields | None = Field(default=None, alias="humanFields")


class WorkDocEvidence(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId")
    sender: str | None
    timestamp: datetime
    text: str


class WorkDocFact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fact: str
    source_message_ids: list[str] = Field(alias="sourceMessageIds")


class WorkDocDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workdoc_id: str = Field(alias="workdocId")
    candidate_id: str = Field(alias="candidateId")
    title: str
    type: PromotedRequirementType
    project_or_repo: str = Field(alias="projectOrRepo")
    working_dir: str | None = Field(default=None, alias="workingDir")
    branch: str | None = None
    background: str
    problem_statement: str = Field(alias="problemStatement")
    expected_outcome: str = Field(alias="expectedOutcome")
    evidence: list[WorkDocEvidence]
    facts: list[WorkDocFact]
    assumptions: list[str]
    constraints: list[str]
    acceptance_criteria: list[str] = Field(alias="acceptanceCriteria")
    out_of_scope: list[str] = Field(alias="outOfScope")
    human_notes: str | None = Field(default=None, alias="humanNotes")
    status: WorkDocDraftStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AgentInputTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_or_repo: str = Field(alias="projectOrRepo")
    working_dir: str | None = Field(default=None, alias="workingDir")
    branch: str | None = None


class AgentInputTask(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    type: PromotedRequirementType
    objective: str
    context: str
    actual_behavior: str | None = Field(default=None, alias="actualBehavior")
    expected_behavior: str | None = Field(default=None, alias="expectedBehavior")
    desired_behavior: str | None = Field(default=None, alias="desiredBehavior")
    constraints: list[str]
    acceptance_criteria: list[str] = Field(alias="acceptanceCriteria")
    out_of_scope: list[str] = Field(alias="outOfScope")


class AgentInputEvidence(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: Literal["chat"] = "chat"
    message_id: str = Field(alias="messageId")
    sender: str | None
    timestamp: datetime
    text: str


class ExecutionPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    require_plan_before_edit: bool = Field(alias="requirePlanBeforeEdit")
    allow_code_edit: bool = Field(alias="allowCodeEdit")
    allow_test_run: bool = Field(alias="allowTestRun")
    allow_git_commit: bool = Field(alias="allowGitCommit")
    allow_push: bool = Field(alias="allowPush")
    forbidden_actions: list[str] = Field(alias="forbiddenActions")


class OutputContract(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    require_summary: bool = Field(alias="requireSummary")
    require_changed_files: bool = Field(alias="requireChangedFiles")
    require_tests: bool = Field(alias="requireTests")
    require_open_questions: bool = Field(alias="requireOpenQuestions")
    require_diff: bool = Field(alias="requireDiff")


class AgentInputPack(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pack_id: str = Field(alias="packId")
    workdoc_id: str = Field(alias="workdocId")
    candidate_id: str = Field(alias="candidateId")
    target: AgentInputTarget
    task: AgentInputTask
    evidence: list[AgentInputEvidence]
    execution_policy: ExecutionPolicy = Field(alias="executionPolicy")
    output_contract: OutputContract = Field(alias="outputContract")
    created_at: datetime = Field(alias="createdAt")


class RequirementPromotionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    candidate: CandidateRequirement
    decision: HumanReviewDecision
    write_inbox: bool = Field(default=False, alias="writeInbox")


class RequirementPromotionResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workdoc_draft: WorkDocDraft = Field(alias="workdocDraft")
    agent_input_pack: AgentInputPack = Field(alias="agentInputPack")
    agent_brief_markdown: str = Field(alias="agentBriefMarkdown")
    inbox_path: str | None = Field(default=None, alias="inboxPath")

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PolicyDecisionType, RiskLevel, WorkflowStatus
from app.models.task_candidate import TaskCandidate
from app.models.workdoc import WorkDoc
from app.schemas.workdoc import (
    AgentConfig,
    ExecutionConfig,
    GitConfig,
    ReviewConfig,
    TestConfig,
    WorkDocFromMessagesRequest,
    WorkDocFromTaskCandidateRequest,
    WorkDocUpdateRequest,
)
from app.services.errors import InvalidStateError, NotFoundError
from app.services.message_store import MessageStore
from app.services.policy_gate import PolicyGate


class WorkDocService:
    _UPDATABLE_FIELDS: tuple[str, ...] = (
        "title",
        "problem_summary",
        "observed_behavior",
        "expected_behavior",
        "constraints",
        "acceptance_criteria",
        "evidence_message_ids",
        "uncertainties",
    )

    def __init__(self, db: Session):
        self.db = db
        self.policy_gate = PolicyGate(db)

    def create_from_messages(self, request: WorkDocFromMessagesRequest) -> WorkDoc:
        messages = MessageStore(self.db).get_messages_by_ids(request.message_ids)
        if len(messages) != len(request.message_ids):
            found_ids = {message.id for message in messages}
            missing = [message_id for message_id in request.message_ids if message_id not in found_ids]
            raise NotFoundError(f"messages not found: {missing}")

        if any(message.platform in {"personal_wechat", "wechat_database"} for message in messages):
            raise InvalidStateError("WeChat messages must enter WorkDoc flow through Segment and TaskCandidate")

        return self._create_workdoc(
            text="\n".join(message.text for message in messages).strip(),
            evidence_message_ids=request.message_ids,
            repo_name=request.repo_name,
            repo_path=request.repo_path,
            branch_base=request.branch_base,
            execution=request.execution,
            test=request.test,
            agent=request.agent,
            git=request.git,
            review=request.review,
        )

    def create_from_task_candidate(self, request: WorkDocFromTaskCandidateRequest) -> WorkDoc:
        candidate = self.db.get(TaskCandidate, request.task_candidate_id)
        if candidate is None:
            raise NotFoundError(f"task candidate not found: {request.task_candidate_id}")
        if candidate.status != WorkflowStatus.READY_FOR_WORKDOC.value:
            raise InvalidStateError("TaskCandidate must be READY_FOR_WORKDOC before conversion")
        return self._create_workdoc(
            text=candidate.command_text,
            evidence_message_ids=candidate.evidence_message_ids,
            repo_name=request.repo_name,
            repo_path=candidate.repo_path or request.repo_path,
            branch_base=request.branch_base,
            execution=request.execution,
            test=request.test or TestConfig(),
            agent=request.agent,
            git=request.git,
            review=request.review,
            explicit_acceptance_criteria=candidate.acceptance_criteria,
        )

    def list_workdocs(
        self,
        status: str | None = None,
        risk_level: str | None = None,
        repo_name: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[WorkDoc]:
        stmt = select(WorkDoc)
        if status is not None:
            stmt = stmt.where(WorkDoc.status == status)
        if risk_level is not None:
            stmt = stmt.where(WorkDoc.risk_level == risk_level)
        if repo_name is not None:
            stmt = stmt.where(WorkDoc.repo_name == repo_name)
        stmt = stmt.order_by(WorkDoc.id.asc())
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def get_workdoc(self, workdoc_id: int) -> WorkDoc:
        workdoc = self.db.get(WorkDoc, workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {workdoc_id}")
        self._ensure_config_defaults(workdoc)
        return workdoc

    def validate(self, workdoc_id: int) -> tuple[WorkDoc, bool, list[str]]:
        workdoc = self.get_workdoc(workdoc_id)
        if workdoc.status not in {
            WorkflowStatus.WORKDOC_DRAFTED.value,
            WorkflowStatus.HUMAN_REVIEW_REQUIRED.value,
            WorkflowStatus.POLICY_BLOCKED.value,
        }:
            raise InvalidStateError(f"cannot validate WorkDoc from status {workdoc.status}")

        decision = self.policy_gate.decide_workdoc_validation(workdoc, record=False)
        if decision.reasons:
            workdoc.status = WorkflowStatus.HUMAN_REVIEW_REQUIRED.value
            self._record_policy_decision(workdoc, decision, commit=False)
            self.db.commit()
            self.db.refresh(workdoc)
            return workdoc, False, decision.reasons

        workdoc.status = WorkflowStatus.WORKDOC_VALIDATED.value
        self._record_policy_decision(workdoc, decision, commit=False)
        self.db.commit()
        self.db.refresh(workdoc)
        return workdoc, True, []

    def approve(self, workdoc_id: int) -> WorkDoc:
        workdoc = self.get_workdoc(workdoc_id)
        if workdoc.status != WorkflowStatus.WORKDOC_VALIDATED.value:
            raise InvalidStateError("only WORKDOC_VALIDATED WorkDocs can be approved")

        approved_at = datetime.now(timezone.utc)
        workdoc.status = WorkflowStatus.WORKDOC_APPROVED.value
        workdoc.approved_at = approved_at

        decision = self.policy_gate.decide_agent_execution(workdoc, record=False)
        if decision.decision == PolicyDecisionType.BLOCK.value:
            workdoc.status = WorkflowStatus.POLICY_BLOCKED.value
            workdoc.approved_at = None
            self._record_agent_execution_decision(workdoc, decision, commit=False)
            self.db.commit()
            raise InvalidStateError("; ".join(decision.reasons))

        workdoc.status = WorkflowStatus.APPROVED_FOR_AGENT.value
        self._record_agent_execution_decision(workdoc, decision, commit=False)
        self.db.commit()
        self.db.refresh(workdoc)
        return workdoc

    def update(self, workdoc_id: int, request: WorkDocUpdateRequest) -> WorkDoc:
        workdoc = self.get_workdoc(workdoc_id)
        if workdoc.status not in {
            WorkflowStatus.WORKDOC_DRAFTED.value,
            WorkflowStatus.HUMAN_REVIEW_REQUIRED.value,
            WorkflowStatus.POLICY_BLOCKED.value,
        }:
            raise InvalidStateError(
                f"only draft, human-review, or policy-blocked WorkDocs can be updated; current status: {workdoc.status}"
            )

        for field in self._UPDATABLE_FIELDS:
            value = getattr(request, field, None)
            if value is not None:
                setattr(workdoc, field, value)

        review_update = request.review.model_dump(exclude_unset=True) if request.review is not None else {}
        for config_field in ("execution", "test", "agent", "git", "review"):
            value = getattr(request, config_field, None)
            if value is not None:
                existing = getattr(workdoc, config_field) or {}
                update = review_update if config_field == "review" else value.model_dump(exclude_unset=True)
                merged = {**existing, **update}
                setattr(workdoc, config_field, merged)

        if "risk_level" in review_update:
            workdoc.risk_level = review_update["risk_level"]
        if request.acceptance_criteria:
            workdoc.uncertainties = [
                item for item in (workdoc.uncertainties or []) if "acceptance criteria" not in item.lower()
            ]

        workdoc.status = WorkflowStatus.WORKDOC_DRAFTED.value
        workdoc.approved_at = None
        self.db.commit()
        self.db.refresh(workdoc)
        return workdoc

    def _record_policy_decision(self, workdoc: WorkDoc, decision, commit: bool = False) -> None:
        self.policy_gate.record_result(
            workdoc_id=workdoc.id,
            agent_run_id=None,
            result=decision,
            metadata={"status": workdoc.status},
            commit=commit,
        )

    def _record_agent_execution_decision(self, workdoc: WorkDoc, decision, commit: bool = False) -> None:
        self.policy_gate.record_result(
            workdoc_id=workdoc.id,
            agent_run_id=None,
            result=decision,
            metadata={"status": workdoc.status},
            commit=commit,
        )

    def _create_workdoc(
        self,
        text: str,
        evidence_message_ids: list[int],
        repo_name: str,
        repo_path: str,
        branch_base: str,
        execution: ExecutionConfig | None,
        test: TestConfig | None,
        agent: AgentConfig | None,
        git: GitConfig | None,
        review: ReviewConfig | None,
        explicit_acceptance_criteria: list[str] | None = None,
    ) -> WorkDoc:
        combined_text = text.strip()
        acceptance_criteria = explicit_acceptance_criteria or _extract_acceptance_criteria(combined_text)
        risk_level = _infer_risk_level(combined_text)
        review_config = review or ReviewConfig(risk_level=risk_level)
        workdoc = WorkDoc(
            title=_make_title(combined_text),
            repo_name=repo_name,
            repo_path=repo_path,
            branch_base=branch_base,
            problem_summary=combined_text or "No message text provided.",
            observed_behavior=_extract_observed_behavior(combined_text),
            expected_behavior=_extract_expected_behavior(combined_text),
            constraints=_extract_constraints(combined_text),
            acceptance_criteria=acceptance_criteria,
            evidence_message_ids=evidence_message_ids,
            uncertainties=[] if acceptance_criteria else ["acceptance criteria could not be inferred"],
            execution=(execution or ExecutionConfig()).model_dump(),
            test=(test or _infer_test_config(combined_text)).model_dump(),
            agent=(agent or AgentConfig()).model_dump(),
            git=(git or GitConfig()).model_dump(),
            review=review_config.model_dump(),
            risk_level=review_config.risk_level,
            status=WorkflowStatus.WORKDOC_DRAFTED.value,
        )
        self.db.add(workdoc)
        self.db.commit()
        self.db.refresh(workdoc)
        return workdoc

    def _ensure_config_defaults(self, workdoc: WorkDoc) -> None:
        if not workdoc.execution:
            workdoc.execution = ExecutionConfig().model_dump()
        if not workdoc.test:
            workdoc.test = TestConfig().model_dump()
        if not workdoc.agent:
            workdoc.agent = AgentConfig().model_dump()
        if not workdoc.git:
            workdoc.git = GitConfig().model_dump()
        if not workdoc.review:
            workdoc.review = ReviewConfig(risk_level=workdoc.risk_level).model_dump()


def _make_title(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else "Untitled task"
    return first_line[:80]


def _extract_observed_behavior(text: str) -> str | None:
    lowered = text.lower()
    if any(token in lowered for token in ["no response", "broken", "does not", "failed"]):
        return text
    if any(token in text for token in ["没反应", "失败", "错误", "坏了"]):
        return text
    return None


def _extract_expected_behavior(text: str) -> str | None:
    lowered = text.lower()
    if any(token in lowered for token in ["should", "expected"]) or any(
        token in text for token in ["应该", "需要", "跳转"]
    ):
        return text
    return None


def _extract_constraints(text: str) -> list[str]:
    constraints: list[str] = []
    if "别重构" in text or "不要重构" in text or "do not refactor" in text.lower():
        constraints.append("Do not refactor unrelated code.")
    if "只修" in text or "only fix" in text.lower():
        constraints.append("Keep the change narrowly scoped.")
    return constraints


def _extract_acceptance_criteria(text: str) -> list[str]:
    if any(token in text for token in ["应该", "跳转", "/settings"]) or any(
        token in text.lower() for token in ["should", "expected"]
    ):
        return [f"Behavior matches the requested outcome: {text[:180]}"]
    return []


def _infer_risk_level(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["payment", "auth", "secret", ".env", "production", "deploy"]):
        return RiskLevel.HIGH.value
    if any(token in text for token in ["支付", "认证", "密钥", "生产", "部署"]):
        return RiskLevel.HIGH.value
    return RiskLevel.LOW.value


def _infer_test_config(text: str) -> TestConfig:
    lowered = text.lower()
    if "pytest" in lowered:
        return TestConfig(commands=["python -m pytest"], required=True)
    if "npm test" in lowered:
        return TestConfig(commands=["npm test"], required=True)
    return TestConfig()

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PolicyDecisionType, RiskLevel, WorkflowStatus
from app.models.workdoc import WorkDoc
from app.schemas.workdoc import AgentConfig, ExecutionConfig, GitConfig, ReviewConfig, TestConfig, WorkDocFromMessagesRequest
from app.services.errors import InvalidStateError, NotFoundError
from app.services.message_store import MessageStore
from app.services.policy_gate import PolicyGate


class WorkDocService:
    def __init__(self, db: Session):
        self.db = db
        self.policy_gate = PolicyGate(db)

    def create_from_messages(self, request: WorkDocFromMessagesRequest) -> WorkDoc:
        messages = MessageStore(self.db).get_messages_by_ids(request.message_ids)
        if len(messages) != len(request.message_ids):
            found_ids = {message.id for message in messages}
            missing = [message_id for message_id in request.message_ids if message_id not in found_ids]
            raise NotFoundError(f"messages not found: {missing}")

        combined_text = "\n".join(message.text for message in messages).strip()
        title = _make_title(combined_text)
        acceptance_criteria = _extract_acceptance_criteria(combined_text)
        risk_level = _infer_risk_level(combined_text)
        review = request.review or ReviewConfig(risk_level=risk_level)
        execution = request.execution or ExecutionConfig()
        test = request.test or _infer_test_config(combined_text)
        agent = request.agent or AgentConfig()
        git = request.git or GitConfig()

        workdoc = WorkDoc(
            title=title,
            repo_name=request.repo_name,
            repo_path=request.repo_path,
            branch_base=request.branch_base,
            problem_summary=combined_text or "No message text provided.",
            observed_behavior=_extract_observed_behavior(combined_text),
            expected_behavior=_extract_expected_behavior(combined_text),
            constraints=_extract_constraints(combined_text),
            acceptance_criteria=acceptance_criteria,
            evidence_message_ids=request.message_ids,
            uncertainties=[] if acceptance_criteria else ["acceptance criteria could not be inferred"],
            execution=execution.model_dump(),
            test=test.model_dump(),
            agent=agent.model_dump(),
            git=git.model_dump(),
            review=review.model_dump(),
            risk_level=review.risk_level,
            status=WorkflowStatus.WORKDOC_DRAFTED.value,
        )
        self.db.add(workdoc)
        self.db.commit()
        self.db.refresh(workdoc)
        return workdoc

    def list_workdocs(self) -> list[WorkDoc]:
        return list(self.db.scalars(select(WorkDoc).order_by(WorkDoc.id.asc())))

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

        decision = self.policy_gate.decide_workdoc_validation(workdoc)
        if decision.reasons:
            workdoc.status = WorkflowStatus.HUMAN_REVIEW_REQUIRED.value
            self.db.commit()
            self.db.refresh(workdoc)
            return workdoc, False, decision.reasons

        workdoc.status = WorkflowStatus.WORKDOC_VALIDATED.value
        self.db.commit()
        self.db.refresh(workdoc)
        return workdoc, True, []

    def approve(self, workdoc_id: int) -> WorkDoc:
        workdoc = self.get_workdoc(workdoc_id)
        if workdoc.status != WorkflowStatus.WORKDOC_VALIDATED.value:
            raise InvalidStateError("only WORKDOC_VALIDATED WorkDocs can be approved")

        workdoc.status = WorkflowStatus.WORKDOC_APPROVED.value
        workdoc.approved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(workdoc)

        decision = self.policy_gate.decide_agent_execution(workdoc)
        if decision.decision == PolicyDecisionType.BLOCK.value:
            workdoc.status = WorkflowStatus.POLICY_BLOCKED.value
            self.db.commit()
            raise InvalidStateError("; ".join(decision.reasons))

        workdoc.status = WorkflowStatus.APPROVED_FOR_AGENT.value
        self.db.commit()
        self.db.refresh(workdoc)
        return workdoc

    def _ensure_config_defaults(self, workdoc: WorkDoc) -> None:
        changed = False
        if not workdoc.execution:
            workdoc.execution = ExecutionConfig().model_dump()
            changed = True
        if not workdoc.test:
            workdoc.test = TestConfig().model_dump()
            changed = True
        if not workdoc.agent:
            workdoc.agent = AgentConfig().model_dump()
            changed = True
        if not workdoc.git:
            workdoc.git = GitConfig().model_dump()
            changed = True
        if not workdoc.review:
            workdoc.review = ReviewConfig(risk_level=workdoc.risk_level).model_dump()
            changed = True
        if changed:
            self.db.commit()
            self.db.refresh(workdoc)


def _make_title(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else "Untitled task"
    return first_line[:80]


def _extract_observed_behavior(text: str) -> str | None:
    if any(token in text.lower() for token in ["no response", "broken", "does not", "failed"]):
        return text
    if any(token in text for token in ["没反应", "失败", "错误", "坏了"]):
        return text
    return None


def _extract_expected_behavior(text: str) -> str | None:
    markers = ["should", "expected", "应该", "需要", "跳转"]
    if any(marker in text.lower() for marker in markers[:2]) or any(marker in text for marker in markers[2:]):
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

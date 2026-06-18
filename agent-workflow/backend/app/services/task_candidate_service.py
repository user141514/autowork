from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.enums import WorkflowStatus
from app.models.message_segment import MessageSegment
from app.models.task_candidate import TaskCandidate
from app.schemas.task_candidate import TaskCandidateFromSegmentRequest, TaskCandidateUpdateRequest
from app.services.errors import InvalidStateError, NotFoundError


class TaskCandidateService:
    def __init__(self, db: Session):
        self.db = db

    def create_from_segment(self, request: TaskCandidateFromSegmentRequest) -> TaskCandidate:
        segment = self.db.get(MessageSegment, request.segment_id)
        if segment is None:
            raise NotFoundError(f"segment not found: {request.segment_id}")
        mention = get_settings().workbot_mention
        if mention not in segment.text:
            raise InvalidStateError(f"only {mention} commands can enter task flow")

        command_text = _command_text_from_segment(segment.text, mention)
        if not command_text:
            raise InvalidStateError("WorkBot command text is empty")
        missing_fields = _missing_fields(repo_path=None, acceptance_criteria=[])

        candidate = TaskCandidate(
            segment_id=segment.id,
            room_id=segment.room_id,
            command_text=command_text,
            evidence_message_ids=segment.message_ids,
            missing_fields=missing_fields,
            confidence="high",
            status=WorkflowStatus.NEED_CLARIFICATION.value if missing_fields else WorkflowStatus.READY_FOR_WORKDOC.value,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def list_candidates(self) -> list[TaskCandidate]:
        return list(self.db.scalars(select(TaskCandidate).order_by(TaskCandidate.id.asc())))

    def get_candidate(self, candidate_id: int) -> TaskCandidate:
        candidate = self.db.get(TaskCandidate, candidate_id)
        if candidate is None:
            raise NotFoundError(f"task candidate not found: {candidate_id}")
        return candidate

    def update_candidate(self, candidate_id: int, request: TaskCandidateUpdateRequest) -> TaskCandidate:
        candidate = self.get_candidate(candidate_id)
        if candidate.status == WorkflowStatus.CONVERTED_TO_WORKDOC.value:
            raise InvalidStateError("converted TaskCandidate cannot be updated")
        if request.repo_path is not None:
            candidate.repo_path = request.repo_path
        if request.acceptance_criteria is not None:
            candidate.acceptance_criteria = request.acceptance_criteria
        candidate.missing_fields = _missing_fields(candidate.repo_path, candidate.acceptance_criteria)
        candidate.status = (
            WorkflowStatus.READY_FOR_WORKDOC.value
            if not candidate.missing_fields
            else WorkflowStatus.NEED_CLARIFICATION.value
        )
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def mark_converted(self, candidate_id: int, workdoc_id: int) -> TaskCandidate:
        candidate = self.get_candidate(candidate_id)
        candidate.workdoc_id = workdoc_id
        candidate.status = WorkflowStatus.CONVERTED_TO_WORKDOC.value
        self.db.commit()
        self.db.refresh(candidate)
        return candidate


def _missing_fields(repo_path: str | None, acceptance_criteria: list[str] | None) -> list[str]:
    missing: list[str] = []
    if not repo_path:
        missing.append("repo_path")
    if not acceptance_criteria:
        missing.append("acceptance_criteria")
    return missing


def _command_text_from_segment(text: str, mention: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    command_lines = [line for line in lines if mention in line]
    if not command_lines:
        return ""
    command = command_lines[-1].split(mention, 1)[1].strip()
    context = [line for line in lines if mention not in line]
    if command in {"记录为任务", "生成WorkDoc", "生成 WorkDoc"}:
        return "\n".join(context).strip()
    return "\n".join([*context, command]).strip()

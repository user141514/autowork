import re

from sqlalchemy.orm import Session

from app.adapters.chat.mock_chat_adapter import MockChatAdapter
from app.adapters.chat.wxauto_adapter import PersonalWeChatAdapter
from app.config import get_settings
from app.models.agent_run import AgentRun
from app.models.feedback_log import FeedbackLog
from app.models.task_candidate import TaskCandidate
from app.models.workdoc import WorkDoc
from app.services.errors import InvalidStateError, NotFoundError, PolicyViolationError
from app.services.report_service import ReportService


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db

    def task_candidate_feedback(self, candidate_id: int, room_id: str, adapter_type: str) -> FeedbackLog:
        candidate = self.db.get(TaskCandidate, candidate_id)
        if candidate is None:
            raise NotFoundError(f"task candidate not found: {candidate_id}")
        missing = ", ".join(candidate.missing_fields or []) or "none"
        text = f"TaskCandidate {candidate.id} status: {candidate.status}. Missing fields: {missing}."
        return self._send(room_id, adapter_type, "task_candidate", candidate.id, text)

    def workdoc_feedback(self, workdoc_id: int, room_id: str, adapter_type: str) -> FeedbackLog:
        workdoc = self.db.get(WorkDoc, workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {workdoc_id}")
        text = f"WorkDoc {workdoc.id} status: {workdoc.status}. Title: {workdoc.title}"
        return self._send(room_id, adapter_type, "workdoc", workdoc.id, text)

    def agent_run_feedback(self, agent_run_id: int, room_id: str, adapter_type: str) -> FeedbackLog:
        agent_run = self.db.get(AgentRun, agent_run_id)
        if agent_run is None:
            raise NotFoundError(f"agent run not found: {agent_run_id}")
        text = f"AgentRun {agent_run.id} status: {agent_run.status}. Summary: {agent_run.result_summary}"
        return self._send(room_id, adapter_type, "agent_run", agent_run.id, text)

    def report_feedback(self, workdoc_id: int, room_id: str, adapter_type: str) -> FeedbackLog:
        report = ReportService(self.db).workdoc_report(workdoc_id)
        summary = "\n".join(report.splitlines()[:12])
        return self._send(room_id, adapter_type, "report", workdoc_id, summary)

    def _send(self, room_id: str, adapter_type: str, target_type: str, target_id: int, text: str) -> FeedbackLog:
        safe_text = _redact_feedback(text)
        log = FeedbackLog(
            room_id=room_id,
            adapter_type=adapter_type,
            target_type=target_type,
            target_id=target_id,
            text=safe_text,
            status="created",
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        try:
            if adapter_type == "mock":
                MockChatAdapter().send_message(room_id, safe_text)
                log.status = "sent_mock"
            elif adapter_type in {"wechat", "personal_wechat", "wxauto"}:
                if not get_settings().wechat_send_enabled:
                    raise PolicyViolationError("WECHAT_SEND_DISABLED")
                PersonalWeChatAdapter().send_message(room_id, safe_text)
                log.status = "sent"
            else:
                raise InvalidStateError(f"unsupported feedback adapter: {adapter_type}")
        except Exception as exc:
            log.status = "blocked" if isinstance(exc, PolicyViolationError) else "failed"
            log.error_code = str(exc)
        self.db.commit()
        self.db.refresh(log)
        return log


def _redact_feedback(text: str) -> str:
    text = re.sub(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    text = re.sub(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[REDACTED_EMAIL]", text)
    return text[:3500]

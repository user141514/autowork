from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.adapters.agent.base import BaseAgentRunner
from app.adapters.agent.claude_cli_runner import ClaudeCliRunner
from app.adapters.agent.gagent_desktop_runner import GAgentDesktopRunner
from app.adapters.agent.mock_agent_runner import MockAgentRunner
from app.config import get_settings
from app.models.agent_run import AgentRun
from app.models.enums import AgentType, PolicyDecisionType, WorkflowStatus
from app.models.workdoc import WorkDoc
from app.schemas.agent_run import AgentRunFromWorkDocRequest
from app.services.errors import InvalidStateError, NotFoundError
from app.services.git_inspector import GitInspector
from app.services.policy_gate import PolicyGate
from app.services.repo_context_builder import RepoContextBuilder


RUNNERS: dict[str, type[BaseAgentRunner]] = {
    AgentType.MOCK.value: MockAgentRunner,
    AgentType.CLAUDE_CLI.value: ClaudeCliRunner,
    AgentType.GAGENT_DESKTOP.value: GAgentDesktopRunner,
}


class AgentRunnerService:
    def __init__(self, db: Session):
        self.db = db
        self.policy_gate = PolicyGate(db)
        self.git_inspector = GitInspector()

    def run_from_workdoc(self, workdoc_id: int, request: AgentRunFromWorkDocRequest) -> AgentRun:
        workdoc = self.db.get(WorkDoc, workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {workdoc_id}")
        decision = self.policy_gate.decide_agent_execution(workdoc)
        if decision.decision != PolicyDecisionType.ALLOW.value:
            workdoc.status = WorkflowStatus.POLICY_BLOCKED.value
            self.db.commit()
            raise InvalidStateError("; ".join(decision.reasons))

        agent_type = request.agent_type or (workdoc.agent or {}).get("preferred_runner") or AgentType.MOCK.value
        runner_cls = RUNNERS.get(agent_type)
        if runner_cls is None:
            raise InvalidStateError(f"unsupported agent_type: {agent_type}")

        repo_path = request.repo_path or workdoc.repo_path
        repo = Path(repo_path).resolve()
        self.git_inspector.ensure_git_repo(repo)
        repo_context = RepoContextBuilder().build(workdoc, str(repo))
        timeout_seconds = (
            request.timeout_seconds
            or int((workdoc.agent or {}).get("timeout_seconds") or 0)
            or get_settings().default_agent_timeout_seconds
        )
        input_json = {
            "workdoc": {
                "id": workdoc.id,
                "title": workdoc.title,
                "status": workdoc.status,
                "execution": workdoc.execution or {},
                "test": workdoc.test or {},
                "agent": workdoc.agent or {},
                "git": workdoc.git or {},
                "review": workdoc.review or {},
            },
            "repo_context": repo_context.model_dump(),
        }
        agent_run = AgentRun(
            workdoc_id=workdoc.id,
            agent_type=agent_type,
            repo_path=str(repo),
            status=WorkflowStatus.AGENT_RUN_CREATED.value,
            input_json=input_json,
        )
        self.db.add(agent_run)
        self.db.commit()
        self.db.refresh(agent_run)

        agent_run.status = WorkflowStatus.AGENT_RUNNING.value
        agent_run.started_at = datetime.now(timezone.utc)
        self.db.commit()

        result = runner_cls().run(workdoc, str(repo), timeout_seconds, input_json)
        changed_files = self.git_inspector.changed_files(repo)
        diff_summary = self.git_inspector.diff_summary(repo)
        diff_stats = self.git_inspector.diff_stats(repo)
        patch_decision = self.policy_gate.decide_patch(workdoc, agent_run, changed_files, diff_stats)

        agent_run.command = result.command
        agent_run.stdout_log = result.stdout
        agent_run.stderr_log = result.stderr
        agent_run.changed_files = changed_files
        agent_run.diff_summary = diff_summary
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.result_summary = result.result_summary
        if result.exit_code != 0:
            agent_run.status = WorkflowStatus.HUMAN_REVIEW_REQUIRED.value
        elif patch_decision.decision == PolicyDecisionType.ALLOW.value:
            agent_run.status = WorkflowStatus.PATCH_CREATED.value
        else:
            agent_run.status = WorkflowStatus.POLICY_BLOCKED.value
        workdoc.status = agent_run.status
        self.db.commit()
        self.db.refresh(agent_run)
        return agent_run

    def get_agent_run(self, agent_run_id: int) -> AgentRun:
        agent_run = self.db.get(AgentRun, agent_run_id)
        if agent_run is None:
            raise NotFoundError(f"agent run not found: {agent_run_id}")
        return agent_run

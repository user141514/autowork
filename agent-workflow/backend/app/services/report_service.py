from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun
from app.models.chat_message import ChatMessage
from app.models.git_operation import GitOperation
from app.models.policy_decision import PolicyDecision
from app.models.test_run import TestRun
from app.models.workdoc import WorkDoc
from app.services.errors import NotFoundError


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def workdoc_report(self, workdoc_id: int) -> str:
        workdoc = self.db.get(WorkDoc, workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {workdoc_id}")

        messages = list(
            self.db.scalars(select(ChatMessage).where(ChatMessage.id.in_(workdoc.evidence_message_ids or [])))
        )
        agent_runs = list(self.db.scalars(select(AgentRun).where(AgentRun.workdoc_id == workdoc.id)))
        test_runs = list(self.db.scalars(select(TestRun).where(TestRun.workdoc_id == workdoc.id)))
        git_ops = list(self.db.scalars(select(GitOperation).where(GitOperation.workdoc_id == workdoc.id)))
        policies = list(self.db.scalars(select(PolicyDecision).where(PolicyDecision.workdoc_id == workdoc.id)))

        lines = self._workdoc_summary(workdoc)
        lines.extend(["", "## Source Evidence"])
        lines.extend([f"- #{message.id} [{message.room_id}] {message.text}" for message in messages] or ["- None"])
        lines.extend(["", "## Agent Execution Logs"])
        if agent_runs:
            for run in agent_runs:
                lines.extend(self._agent_run_lines(run))
        else:
            lines.append("- No AgentRun recorded.")

        lines.extend(["", "## Test Results"])
        if test_runs:
            for test_run in test_runs:
                lines.extend(
                    [
                        f"- TestRun {test_run.id}: {test_run.status}",
                        f"  Command: {test_run.command or '(none)'}",
                        f"  Exit code: {test_run.exit_code}",
                    ]
                )
        else:
            lines.append("- No TestRun recorded.")

        lines.extend(["", "## Policy Decisions"])
        lines.extend(self._policy_lines(policies))

        lines.extend(["", "## Git Operations"])
        if git_ops:
            for operation in git_ops:
                lines.extend(
                    [
                        f"- GitOperation {operation.id}: {operation.status}",
                        f"  Branch: {operation.branch_name or '(none)'}",
                        f"  Commit: {operation.commit_hash or '(dry-run or unavailable)'}",
                        f"  PR: {operation.pr_url or '(none)'}",
                        f"  Changed files: {', '.join(operation.changed_files or []) or '(none)'}",
                        "  Diff summary:",
                        _indent(operation.diff_summary or "(no diff summary)"),
                    ]
                )
        else:
            lines.append("- No GitOperation recorded.")

        lines.extend(["", "## Final Status", workdoc.status])
        return "\n".join(lines)

    def agent_run_report(self, agent_run_id: int) -> str:
        agent_run = self.db.get(AgentRun, agent_run_id)
        if agent_run is None:
            raise NotFoundError(f"agent run not found: {agent_run_id}")
        workdoc = self.db.get(WorkDoc, agent_run.workdoc_id)
        test_runs = list(self.db.scalars(select(TestRun).where(TestRun.agent_run_id == agent_run.id)))
        policies = list(self.db.scalars(select(PolicyDecision).where(PolicyDecision.agent_run_id == agent_run.id)))
        git_ops = list(self.db.scalars(select(GitOperation).where(GitOperation.agent_run_id == agent_run.id)))

        lines = [
            f"# AgentRun {agent_run.id}",
            "",
            f"WorkDoc: {workdoc.id if workdoc else agent_run.workdoc_id}",
            f"Runner: {agent_run.agent_type}",
            f"Status: {agent_run.status}",
            f"Repo: {agent_run.repo_path}",
            "",
            "## Execution",
            f"Command: {agent_run.command}",
            "",
            "### Stdout",
            _fenced(agent_run.stdout_log),
            "",
            "### Stderr",
            _fenced(agent_run.stderr_log),
            "",
            "## Changed Files",
            *[f"- {item}" for item in (agent_run.changed_files or [])],
            "",
            "## Diff Summary",
            agent_run.diff_summary or "(no diff summary)",
            "",
            "## Test Results",
        ]
        if test_runs:
            lines.extend([f"- TestRun {run.id}: {run.status}" for run in test_runs])
        else:
            lines.append("- No TestRun recorded.")
        lines.extend(["", "## Policy Decisions"])
        lines.extend(self._policy_lines(policies))
        lines.extend(["", "## Git"])
        if git_ops:
            lines.extend([f"- {op.status}: {op.branch_name or '(none)'} {op.commit_hash or ''}" for op in git_ops])
        else:
            lines.append("- No GitOperation recorded.")
        return "\n".join(lines)

    def _workdoc_summary(self, workdoc: WorkDoc) -> list[str]:
        return [
            f"# WorkDoc {workdoc.id}: {workdoc.title}",
            "",
            "## WorkDoc Summary",
            f"Status: {workdoc.status}",
            f"Risk: {(workdoc.review or {}).get('risk_level', workdoc.risk_level)}",
            f"Repository: {workdoc.repo_name} ({workdoc.repo_path})",
            f"Base branch: {workdoc.branch_base}",
            "",
            "### Problem",
            workdoc.problem_summary,
            "",
            "### Acceptance Criteria",
            *[f"- {item}" for item in workdoc.acceptance_criteria],
        ]

    def _agent_run_lines(self, run: AgentRun) -> list[str]:
        return [
            f"- AgentRun {run.id}: {run.agent_type} {run.status}",
            f"  Command: {run.command}",
            f"  Summary: {run.result_summary}",
            f"  Changed files: {', '.join(run.changed_files or []) or '(none)'}",
            "  Diff summary:",
            _indent(run.diff_summary or "(no diff summary)"),
        ]

    def _policy_lines(self, policies: list[PolicyDecision]) -> list[str]:
        if not policies:
            return ["- No policy decision recorded."]
        return [
            f"- PolicyDecision {policy.id}: {policy.stage} -> {policy.decision}; reasons={policy.reasons or []}"
            for policy in policies
        ]


def _indent(text: str) -> str:
    return "\n".join(f"    {line}" for line in text.splitlines())


def _fenced(text: str) -> str:
    return f"```\n{text or ''}\n```"

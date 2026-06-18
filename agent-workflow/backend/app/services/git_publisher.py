from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.agent_run import AgentRun
from app.models.enums import PolicyDecisionType, WorkflowStatus
from app.models.git_operation import GitOperation
from app.models.test_run import TestRun
from app.models.workdoc import WorkDoc
from app.schemas.git_operation import GitCommitRequest, GitDiffRead
from app.services.errors import InvalidStateError, NotFoundError, PolicyViolationError
from app.services.git_inspector import GitInspector
from app.services.policy_gate import PolicyGate
from app.utils.shell import run_command


class GitPublisher:
    def __init__(self, db: Session):
        self.db = db
        self.policy_gate = PolicyGate(db)
        self.git_inspector = GitInspector()

    def diff_for_run(self, agent_run_id: int) -> GitDiffRead:
        agent_run, _workdoc, repo = self._load_context(agent_run_id)
        changed_files = self.git_inspector.changed_files(repo)
        diff_stats = self.git_inspector.diff_stats(repo)
        diff_summary = self.git_inspector.diff_summary(repo)
        agent_run.changed_files = changed_files
        agent_run.diff_summary = diff_summary
        self.db.commit()
        return GitDiffRead(
            agent_run_id=agent_run.id,
            changed_files=changed_files,
            diff_stats=diff_stats,
            diff_summary=diff_summary,
        )

    def branch_from_run(self, agent_run_id: int, request: GitCommitRequest) -> GitOperation:
        agent_run, workdoc, repo = self._load_context(agent_run_id)
        branch_name = request.branch_name or self.policy_gate.target_branch_name(workdoc)
        if self.policy_gate.is_protected_branch(branch_name):
            raise PolicyViolationError(f"target branch is protected: {branch_name}")

        changed_files = self.git_inspector.changed_files(repo)
        diff_stats = self.git_inspector.diff_stats(repo)
        diff_summary = self.git_inspector.diff_summary(repo)
        dry_run = get_settings().dry_run if request.dry_run is None else request.dry_run

        operation = GitOperation(
            workdoc_id=workdoc.id,
            agent_run_id=agent_run.id,
            branch_name=branch_name,
            changed_files=changed_files,
            diff_stats=diff_stats,
            diff_summary=diff_summary,
            status=WorkflowStatus.APPROVED_FOR_COMMIT.value if dry_run else WorkflowStatus.PATCH_CREATED.value,
        )
        if not dry_run:
            branch = run_command(["git", "checkout", "-B", branch_name], cwd=repo)
            if branch.exit_code != 0:
                operation.status = WorkflowStatus.POLICY_BLOCKED.value
                operation.diff_summary = f"{diff_summary}\n\nBranch failed:\n{branch.stderr}"
                self.db.add(operation)
                self.db.commit()
                raise InvalidStateError(branch.stderr or "git branch failed")

        self.db.add(operation)
        self.db.commit()
        self.db.refresh(operation)
        return operation

    def commit_from_run(self, agent_run_id: int, request: GitCommitRequest) -> GitOperation:
        agent_run, workdoc, repo = self._load_context(agent_run_id)
        if agent_run.status != WorkflowStatus.PATCH_CREATED.value:
            raise InvalidStateError("only PATCH_CREATED AgentRuns can be committed")

        changed_files = self.git_inspector.changed_files(repo)
        if not changed_files:
            raise InvalidStateError("git diff is empty; nothing to commit")
        diff_stats = self.git_inspector.diff_stats(repo)
        diff_summary = self.git_inspector.diff_summary(repo)
        latest_test_status = self._latest_test_status(agent_run.id)
        dry_run = get_settings().dry_run if request.dry_run is None else request.dry_run
        decision = self.policy_gate.decide_commit(
            workdoc=workdoc,
            agent_run=agent_run,
            changed_files=changed_files,
            diff_stats=diff_stats,
            latest_test_status=latest_test_status,
            dry_run=dry_run,
            dangerous_operation="commit",
        )
        if decision.decision != PolicyDecisionType.ALLOW.value:
            workdoc.status = WorkflowStatus.POLICY_BLOCKED.value
            self.db.commit()
            raise PolicyViolationError("; ".join(decision.reasons))

        branch_name = request.branch_name or self.policy_gate.target_branch_name(workdoc)
        if self.policy_gate.is_protected_branch(branch_name):
            raise PolicyViolationError(f"target branch is protected: {branch_name}")

        operation = GitOperation(
            workdoc_id=workdoc.id,
            agent_run_id=agent_run.id,
            branch_name=branch_name,
            changed_files=changed_files,
            diff_stats=diff_stats,
            diff_summary=diff_summary,
            status=WorkflowStatus.APPROVED_FOR_COMMIT.value if dry_run else WorkflowStatus.GIT_COMMITTED.value,
        )
        if dry_run:
            self.db.add(operation)
            self.db.commit()
            self.db.refresh(operation)
            return operation

        branch = run_command(["git", "checkout", "-B", branch_name], cwd=repo)
        if branch.exit_code != 0:
            operation.status = WorkflowStatus.POLICY_BLOCKED.value
            operation.diff_summary = f"{diff_summary}\n\nBranch failed:\n{branch.stderr}"
            self.db.add(operation)
            self.db.commit()
            raise InvalidStateError(branch.stderr or "git branch failed")

        run_command(["git", "add", "-A"], cwd=repo)
        commit_message = request.commit_message or self._commit_message(workdoc)
        commit = run_command(["git", "commit", "-m", commit_message], cwd=repo)
        if commit.exit_code != 0:
            operation.status = WorkflowStatus.POLICY_BLOCKED.value
            operation.diff_summary = f"{diff_summary}\n\nCommit failed:\n{commit.stderr}"
            self.db.add(operation)
            self.db.commit()
            raise InvalidStateError(commit.stderr or "git commit failed")

        commit_hash = run_command(["git", "rev-parse", "HEAD"], cwd=repo)
        operation.commit_hash = commit_hash.stdout.strip()
        workdoc.status = WorkflowStatus.GIT_COMMITTED.value
        self.db.add(operation)
        self.db.commit()
        self.db.refresh(operation)
        return operation

    def push(self, git_operation_id: int) -> GitOperation:
        operation = self._get_operation(git_operation_id)
        workdoc = self.db.get(WorkDoc, operation.workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {operation.workdoc_id}")
        dry_run = get_settings().dry_run
        decision = self.policy_gate.decide_remote_publish(workdoc, "push", dry_run)
        if decision.decision != PolicyDecisionType.ALLOW.value:
            operation.status = WorkflowStatus.POLICY_BLOCKED.value
            self.db.commit()
            raise PolicyViolationError("; ".join(decision.reasons))
        raise InvalidStateError("push interface is reserved but not implemented in Phase 8")

    def create_pr(self, git_operation_id: int) -> GitOperation:
        operation = self._get_operation(git_operation_id)
        workdoc = self.db.get(WorkDoc, operation.workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {operation.workdoc_id}")
        dry_run = get_settings().dry_run
        decision = self.policy_gate.decide_remote_publish(workdoc, "create_pr", dry_run)
        if decision.decision != PolicyDecisionType.ALLOW.value:
            operation.status = WorkflowStatus.POLICY_BLOCKED.value
            self.db.commit()
            raise PolicyViolationError("; ".join(decision.reasons))
        raise InvalidStateError("create PR interface is reserved but not implemented in Phase 8")

    def list_for_workdoc(self, workdoc_id: int) -> list[GitOperation]:
        return list(self.db.scalars(select(GitOperation).where(GitOperation.workdoc_id == workdoc_id)))

    def _load_context(self, agent_run_id: int) -> tuple[AgentRun, WorkDoc, Path]:
        agent_run = self.db.get(AgentRun, agent_run_id)
        if agent_run is None:
            raise NotFoundError(f"agent run not found: {agent_run_id}")
        workdoc = self.db.get(WorkDoc, agent_run.workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {agent_run.workdoc_id}")
        repo = Path(agent_run.repo_path)
        self.git_inspector.ensure_git_repo(repo)
        return agent_run, workdoc, repo

    def _get_operation(self, git_operation_id: int) -> GitOperation:
        operation = self.db.get(GitOperation, git_operation_id)
        if operation is None:
            raise NotFoundError(f"git operation not found: {git_operation_id}")
        return operation

    def _latest_test_status(self, agent_run_id: int) -> str | None:
        test_run = self.db.scalars(
            select(TestRun).where(TestRun.agent_run_id == agent_run_id).order_by(TestRun.id.desc())
        ).first()
        return test_run.status if test_run else None

    def _commit_message(self, workdoc: WorkDoc) -> str:
        template = (workdoc.git or {}).get("commit_message_template") or "WorkDoc {workdoc_id}: {title}"
        return template.format(workdoc_id=workdoc.id, title=workdoc.title, repo_name=workdoc.repo_name)

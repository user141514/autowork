from fnmatch import fnmatch
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.agent_run import AgentRun
from app.models.enums import PolicyDecisionType, RiskLevel, WorkflowStatus
from app.models.policy_decision import PolicyDecision
from app.models.workdoc import WorkDoc
from app.schemas.policy import PolicyDecisionResult


DEFAULT_FORBIDDEN_PATTERNS = [".env", "secrets.*", "*.pem", "*.key"]


class PolicyGate:
    def __init__(self, db: Session | None = None):
        self.db = db

    def decide_workdoc_validation(self, workdoc: WorkDoc) -> PolicyDecisionResult:
        reasons: list[str] = []
        if not workdoc.title.strip():
            reasons.append("title is required")
        if not workdoc.problem_summary.strip():
            reasons.append("problem_summary is required")
        if not workdoc.acceptance_criteria:
            reasons.append("acceptance_criteria is required")
        if not workdoc.evidence_message_ids:
            reasons.append("evidence_message_ids is required")
        if _review_config(workdoc).get("risk_level", workdoc.risk_level) == RiskLevel.HIGH.value:
            reasons.append("high risk WorkDoc requires human review")

        decision = (
            PolicyDecisionType.REQUIRE_HUMAN_REVIEW.value if reasons else PolicyDecisionType.ALLOW.value
        )
        return self._record(
            workdoc_id=workdoc.id,
            agent_run_id=None,
            stage="workdoc_validation",
            decision=decision,
            reasons=reasons,
            metadata={"status": workdoc.status},
        )

    def decide_agent_execution(self, workdoc: WorkDoc) -> PolicyDecisionResult:
        reasons: list[str] = []
        if workdoc.status not in {WorkflowStatus.WORKDOC_APPROVED.value, WorkflowStatus.APPROVED_FOR_AGENT.value}:
            reasons.append("WorkDoc must be approved before AgentRunner execution")
        if not workdoc.acceptance_criteria:
            reasons.append("acceptance_criteria is required")

        decision = PolicyDecisionType.BLOCK.value if reasons else PolicyDecisionType.ALLOW.value
        return self._record(
            workdoc_id=workdoc.id,
            agent_run_id=None,
            stage="agent_execution",
            decision=decision,
            reasons=reasons,
            metadata={"status": workdoc.status},
        )

    def decide_patch(
        self,
        workdoc: WorkDoc,
        agent_run: AgentRun,
        changed_files: list[str],
        diff_stats: dict,
    ) -> PolicyDecisionResult:
        reasons = self._changed_file_reasons(workdoc, changed_files)
        max_diff_lines = int(_agent_config(workdoc).get("max_diff_lines", 1000))
        diff_lines = int(diff_stats.get("total_lines", 0) or 0)
        if diff_lines > max_diff_lines:
            reasons.append(f"diff line count {diff_lines} exceeds max_diff_lines {max_diff_lines}")

        decision = (
            PolicyDecisionType.REQUIRE_HUMAN_REVIEW.value if reasons else PolicyDecisionType.ALLOW.value
        )
        return self._record(
            workdoc_id=workdoc.id,
            agent_run_id=agent_run.id,
            stage="patch_review",
            decision=decision,
            reasons=reasons,
            metadata={"changed_files": changed_files, "diff_stats": diff_stats},
        )

    def decide_commit(
        self,
        workdoc: WorkDoc,
        agent_run: AgentRun,
        changed_files: list[str],
        diff_stats: dict,
        latest_test_status: str | None,
        dry_run: bool,
        dangerous_operation: str,
    ) -> PolicyDecisionResult:
        reasons = self._changed_file_reasons(workdoc, changed_files)
        test_config = _test_config(workdoc)
        if test_config.get("required", False) and latest_test_status != WorkflowStatus.TEST_PASSED.value:
            reasons.append("test.required=true requires latest test status TEST_PASSED before commit")
        if latest_test_status in {WorkflowStatus.TEST_FAILED.value, WorkflowStatus.TEST_TIMEOUT.value}:
            reasons.append(f"latest test status blocks commit: {latest_test_status}")
        if dangerous_operation in {"push", "create_pr"} and dry_run:
            reasons.append(f"dry-run mode blocks dangerous operation: {dangerous_operation}")

        decision = PolicyDecisionType.BLOCK.value if reasons else PolicyDecisionType.ALLOW.value
        return self._record(
            workdoc_id=workdoc.id,
            agent_run_id=agent_run.id,
            stage="commit",
            decision=decision,
            reasons=reasons,
            metadata={
                "changed_files": changed_files,
                "diff_stats": diff_stats,
                "latest_test_status": latest_test_status,
                "dry_run": dry_run,
                "operation": dangerous_operation,
            },
        )

    def decide_remote_publish(
        self,
        workdoc: WorkDoc,
        operation_name: str,
        dry_run: bool,
    ) -> PolicyDecisionResult:
        git_config = _git_config(workdoc)
        reasons: list[str] = []
        if operation_name == "push" and not git_config.get("allow_push", False):
            reasons.append("git.allow_push=false")
        if operation_name == "create_pr" and not git_config.get("allow_pr", False):
            reasons.append("git.allow_pr=false")
        if dry_run:
            reasons.append(f"dry-run mode blocks dangerous operation: {operation_name}")

        decision = PolicyDecisionType.BLOCK.value if reasons else PolicyDecisionType.ALLOW.value
        return self._record(
            workdoc_id=workdoc.id,
            agent_run_id=None,
            stage=operation_name,
            decision=decision,
            reasons=reasons,
            metadata={"dry_run": dry_run},
        )

    def validate_workdoc(self, workdoc: WorkDoc) -> list[str]:
        return self.decide_workdoc_validation(workdoc).reasons

    def validate_changed_files(self, changed_files: list[str], workdoc: WorkDoc | None = None) -> list[str]:
        if workdoc is None:
            return [
                f"sensitive file change is blocked: {path}"
                for path in changed_files
                if _matches_any(path, DEFAULT_FORBIDDEN_PATTERNS)
            ]
        return self._changed_file_reasons(workdoc, changed_files)

    def target_branch_name(self, workdoc: WorkDoc) -> str:
        prefix = _git_config(workdoc).get("branch_prefix", "agent-workflow")
        normalized_prefix = _normalize_branch_part(prefix)
        return f"{normalized_prefix}/workdoc-{workdoc.id}"

    def is_protected_branch(self, branch_name: str) -> bool:
        return branch_name in get_settings().protected_branches

    def _changed_file_reasons(self, workdoc: WorkDoc, changed_files: list[str]) -> list[str]:
        execution = _execution_config(workdoc)
        allowed_paths = execution.get("allowed_paths") or ["**/*"]
        forbidden_paths = execution.get("forbidden_paths") or DEFAULT_FORBIDDEN_PATTERNS
        reasons: list[str] = []
        for file_name in changed_files:
            normalized = _normalize_path(file_name)
            if not _matches_any(normalized, allowed_paths):
                reasons.append(f"changed file is outside execution.allowed_paths: {file_name}")
            if _matches_any(normalized, forbidden_paths):
                reasons.append(f"changed file matches execution.forbidden_paths: {file_name}")
        return reasons

    def _record(
        self,
        workdoc_id: int | None,
        agent_run_id: int | None,
        stage: str,
        decision: str,
        reasons: list[str],
        metadata: dict,
    ) -> PolicyDecisionResult:
        result = PolicyDecisionResult(decision=decision, stage=stage, reasons=reasons, metadata=metadata)
        if self.db is not None:
            self.db.add(
                PolicyDecision(
                    workdoc_id=workdoc_id,
                    agent_run_id=agent_run_id,
                    decision=decision,
                    stage=stage,
                    reasons=reasons,
                    metadata_json=metadata,
                )
            )
            self.db.commit()
        return result


def _execution_config(workdoc: WorkDoc) -> dict:
    return workdoc.execution or {}


def _test_config(workdoc: WorkDoc) -> dict:
    return workdoc.test or {}


def _agent_config(workdoc: WorkDoc) -> dict:
    return workdoc.agent or {}


def _git_config(workdoc: WorkDoc) -> dict:
    return workdoc.git or {}


def _review_config(workdoc: WorkDoc) -> dict:
    return workdoc.review or {}


def _matches_any(file_name: str, patterns: list[str]) -> bool:
    normalized = _normalize_path(file_name)
    basename = PurePosixPath(normalized).name
    if any(pattern in {"*", "**", "**/*"} for pattern in patterns):
        return True
    return any(fnmatch(normalized, pattern) or fnmatch(basename, pattern) for pattern in patterns)


def _normalize_path(file_name: str) -> str:
    return file_name.replace("\\", "/").lstrip("/")


def _normalize_branch_part(value: str) -> str:
    cleaned = value.strip().replace("\\", "/").strip("/")
    return cleaned or "agent-workflow"

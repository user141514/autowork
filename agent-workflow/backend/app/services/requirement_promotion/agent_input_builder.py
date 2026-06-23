import hashlib
from datetime import datetime, timezone

from app.schemas.requirement_promotion import (
    AgentInputEvidence,
    AgentInputPack,
    AgentInputTarget,
    AgentInputTask,
    ExecutionPolicy,
    OutputContract,
    WorkDocDraft,
)


DEFAULT_FORBIDDEN_ACTIONS = [
    "Do not deploy",
    "Do not push to remote",
    "Do not modify unrelated modules",
    "Do not perform broad refactors unless explicitly requested",
    "Do not delete user data",
]


class AgentInputBuilder:
    def build(self, workdoc: WorkDocDraft) -> AgentInputPack:
        return AgentInputPack(
            pack_id=_pack_id(workdoc),
            workdoc_id=workdoc.workdoc_id,
            candidate_id=workdoc.candidate_id,
            target=AgentInputTarget(
                project_or_repo=workdoc.project_or_repo,
                working_dir=workdoc.working_dir,
                branch=workdoc.branch,
            ),
            task=AgentInputTask(
                title=workdoc.title,
                type=workdoc.type,
                objective=workdoc.expected_outcome,
                context=workdoc.background,
                actual_behavior=workdoc.problem_statement if workdoc.type == "bugfix" else None,
                expected_behavior=workdoc.expected_outcome if workdoc.type == "bugfix" else None,
                desired_behavior=workdoc.expected_outcome if workdoc.type != "bugfix" else None,
                constraints=workdoc.constraints,
                acceptance_criteria=workdoc.acceptance_criteria,
                out_of_scope=workdoc.out_of_scope,
            ),
            evidence=[
                AgentInputEvidence(
                    message_id=item.message_id,
                    sender=item.sender,
                    timestamp=item.timestamp,
                    text=item.text,
                )
                for item in workdoc.evidence
            ],
            execution_policy=ExecutionPolicy(
                require_plan_before_edit=True,
                allow_code_edit=True,
                allow_test_run=True,
                allow_git_commit=False,
                allow_push=False,
                forbidden_actions=DEFAULT_FORBIDDEN_ACTIONS,
            ),
            output_contract=OutputContract(
                require_summary=True,
                require_changed_files=True,
                require_tests=True,
                require_open_questions=True,
                require_diff=True,
            ),
            created_at=datetime.now(timezone.utc),
        )


def _pack_id(workdoc: WorkDocDraft) -> str:
    raw = f"{workdoc.workdoc_id}|{workdoc.candidate_id}|{workdoc.title}"
    return "pack_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

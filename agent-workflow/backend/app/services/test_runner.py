from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun
from app.models.enums import WorkflowStatus
from app.models.test_run import TestRun
from app.models.workdoc import WorkDoc
from app.services.errors import InvalidStateError, NotFoundError
from app.utils.shell import run_shell_command


class TestRunner:
    def __init__(self, db: Session):
        self.db = db

    def run_for_agent_run(self, agent_run_id: int) -> TestRun:
        agent_run = self.db.get(AgentRun, agent_run_id)
        if agent_run is None:
            raise NotFoundError(f"agent run not found: {agent_run_id}")
        workdoc = self.db.get(WorkDoc, agent_run.workdoc_id)
        if workdoc is None:
            raise NotFoundError(f"workdoc not found: {agent_run.workdoc_id}")
        if agent_run.status not in {WorkflowStatus.PATCH_CREATED.value, WorkflowStatus.POLICY_BLOCKED.value}:
            raise InvalidStateError(f"cannot run tests for AgentRun status {agent_run.status}")

        commands = (workdoc.test or {}).get("commands") or []
        timeout_seconds = int((workdoc.agent or {}).get("timeout_seconds") or 120)
        test_run = TestRun(
            workdoc_id=workdoc.id,
            agent_run_id=agent_run.id,
            status=WorkflowStatus.TEST_RUNNING.value if commands else WorkflowStatus.TEST_NOT_CONFIGURED.value,
            command=" && ".join(commands),
        )
        self.db.add(test_run)
        self.db.commit()
        self.db.refresh(test_run)

        if not commands:
            test_run.stdout_log = "No test commands configured."
            test_run.finished_at = datetime.now(timezone.utc)
            workdoc.status = WorkflowStatus.TEST_NOT_CONFIGURED.value
            self.db.commit()
            self.db.refresh(test_run)
            return test_run

        started_at = datetime.now(timezone.utc)
        test_run.started_at = started_at
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        final_exit_code = 0
        final_status = WorkflowStatus.TEST_PASSED.value
        repo = Path(agent_run.repo_path)
        for command in commands:
            result = run_shell_command(command, cwd=repo, timeout_seconds=timeout_seconds)
            stdout_parts.append(f"$ {command}\n{result.stdout}")
            if result.stderr:
                stderr_parts.append(f"$ {command}\n{result.stderr}")
            final_exit_code = result.exit_code
            if result.exit_code == 124:
                final_status = WorkflowStatus.TEST_TIMEOUT.value
                break
            if result.exit_code != 0:
                final_status = WorkflowStatus.TEST_FAILED.value
                break

        test_run.status = final_status
        test_run.stdout_log = "\n".join(stdout_parts)
        test_run.stderr_log = "\n".join(stderr_parts)
        test_run.exit_code = final_exit_code
        test_run.finished_at = datetime.now(timezone.utc)
        workdoc.status = final_status
        self.db.commit()
        self.db.refresh(test_run)
        return test_run

    def get_test_run(self, test_run_id: int) -> TestRun:
        test_run = self.db.get(TestRun, test_run_id)
        if test_run is None:
            raise NotFoundError(f"test run not found: {test_run_id}")
        return test_run

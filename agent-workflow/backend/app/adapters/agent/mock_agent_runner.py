from datetime import datetime, timezone
from pathlib import Path

from app.adapters.agent.base import AgentExecutionResult, BaseAgentRunner
from app.models.enums import AgentType
from app.models.workdoc import WorkDoc


class MockAgentRunner(BaseAgentRunner):
    agent_type = AgentType.MOCK.value

    def run(self, workdoc: WorkDoc, repo_path: str, timeout_seconds: int, input_json: dict) -> AgentExecutionResult:
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        patch_file = repo / "agent_workflow_mock_patch.txt"
        line = f"{datetime.now(timezone.utc).isoformat()} workdoc={workdoc.id} title={workdoc.title}\n"
        with patch_file.open("a", encoding="utf-8") as handle:
            handle.write(line)

        command = f"mock-agent --workdoc {workdoc.id} --repo {repo}"
        return AgentExecutionResult(
            command=command,
            exit_code=0,
            stdout=f"Mock agent wrote {patch_file.name}\n",
            stderr="",
            result_summary=f"Mock patch created in {patch_file.name}.",
        )

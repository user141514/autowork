from app.adapters.agent.base import AgentExecutionResult, BaseAgentRunner
from app.config import get_settings
from app.models.enums import AgentType
from app.models.workdoc import WorkDoc
from app.schemas.gagent import AgentRunRequest, AgentRunResult


class GAgentDesktopRunner(BaseAgentRunner):
    agent_type = AgentType.GAGENT_DESKTOP.value

    def run(self, workdoc: WorkDoc, repo_path: str, timeout_seconds: int, input_json: dict) -> AgentExecutionResult:
        settings = get_settings()
        request = AgentRunRequest(
            mode=settings.gagent_desktop_mode,
            workdoc_id=workdoc.id,
            repo_path=repo_path,
            audit_only=True,
            input_json=input_json,
        )
        command = _command_for_request(request, settings.gagent_desktop_endpoint)

        if settings.dry_run or not settings.allow_gagent_desktop:
            return _to_execution_result(
                AgentRunResult(
                    mode=request.mode,
                    audit_only=True,
                    command=command,
                    exit_code=0,
                    stdout="gagent-desktop audit dry-run. Supported modes: cli, http, local_ipc.\n",
                    stderr="",
                    result_summary="gagent-desktop audit planned but not executed because dry-run is enabled or AGENT_WORKFLOW_ALLOW_GAGENT_DESKTOP=false.",
                )
            )

        return _to_execution_result(
            AgentRunResult(
                mode=request.mode,
                audit_only=True,
                command=command,
                exit_code=0,
                stdout="gagent-desktop audit adapter is enabled, but transport implementation is still a stub.\n",
                stderr="",
                result_summary="gagent-desktop audit stub completed without modifying code.",
            )
        )


def _command_for_request(request: AgentRunRequest, endpoint: str | None) -> str:
    if request.mode == "http":
        return f"POST {endpoint or 'http://127.0.0.1:8765/agent-runs'}"
    if request.mode == "cli":
        return f"gagent-desktop audit --workdoc {request.workdoc_id} --repo {request.repo_path}"
    return f"gagent-desktop local-ipc audit --workdoc {request.workdoc_id} --repo {request.repo_path}"


def _to_execution_result(result: AgentRunResult) -> AgentExecutionResult:
    return AgentExecutionResult(
        command=result.command,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        result_summary=result.result_summary,
    )

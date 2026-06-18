from pathlib import Path

from app.adapters.agent.base import AgentExecutionResult, BaseAgentRunner
from app.config import get_settings
from app.models.enums import AgentType
from app.models.workdoc import WorkDoc
from app.utils.shell import run_command


class ClaudeCliRunner(BaseAgentRunner):
    agent_type = AgentType.CLAUDE_CLI.value

    def run(self, workdoc: WorkDoc, repo_path: str, timeout_seconds: int, input_json: dict) -> AgentExecutionResult:
        settings = get_settings()
        repo = Path(repo_path)
        context_file = repo / ".agent_workflow_workdoc.md"
        context_file.write_text(_render_context(workdoc), encoding="utf-8")
        repo_context_path = input_json.get("repo_context", {}).get("generated_context_path")
        repo_context_name = Path(repo_context_path).name if repo_context_path else ".agent_workflow_repo_context.md"
        command = ["claude", "--print", f"Use {context_file.name} and {repo_context_name} as the task contract."]

        if settings.dry_run or not settings.allow_claude_cli:
            return AgentExecutionResult(
                command=" ".join(command),
                exit_code=0,
                stdout=f"Claude CLI dry-run. Context written to {context_file.name}.\n",
                stderr="",
                result_summary="Claude CLI command planned but not executed because dry-run is enabled or AGENT_WORKFLOW_ALLOW_CLAUDE_CLI=false.",
            )

        result = run_command(command, cwd=repo, timeout_seconds=timeout_seconds)
        return AgentExecutionResult(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            result_summary="Claude CLI completed." if result.exit_code == 0 else "Claude CLI failed.",
        )


def _render_context(workdoc: WorkDoc) -> str:
    return "\n".join(
        [
            f"# WorkDoc {workdoc.id}: {workdoc.title}",
            "",
            f"Repository: {workdoc.repo_name}",
            f"Base branch: {workdoc.branch_base}",
            "",
            "## Problem",
            workdoc.problem_summary,
            "",
            "## Expected Behavior",
            workdoc.expected_behavior or "",
            "",
            "## Constraints",
            *[f"- {item}" for item in workdoc.constraints],
            "",
            "## Acceptance Criteria",
            *[f"- {item}" for item in workdoc.acceptance_criteria],
            "",
            "Only use this WorkDoc as the execution contract. Do not infer requirements from chat logs.",
        ]
    )

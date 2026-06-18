from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.workdoc import WorkDoc


@dataclass(frozen=True)
class AgentExecutionResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    result_summary: str


class BaseAgentRunner(ABC):
    agent_type: str

    @abstractmethod
    def run(self, workdoc: WorkDoc, repo_path: str, timeout_seconds: int, input_json: dict) -> AgentExecutionResult:
        raise NotImplementedError

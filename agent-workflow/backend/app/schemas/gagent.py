from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    mode: str = "local_ipc"
    workdoc_id: int
    repo_path: str
    audit_only: bool = True
    input_json: dict = Field(default_factory=dict)


class AgentRunResult(BaseModel):
    mode: str
    audit_only: bool
    command: str
    exit_code: int
    stdout: str
    stderr: str
    result_summary: str

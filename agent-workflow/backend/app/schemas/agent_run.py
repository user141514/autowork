from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentRunFromWorkDocRequest(BaseModel):
    agent_type: str | None = None
    repo_path: str | None = None
    timeout_seconds: int | None = None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workdoc_id: int
    agent_type: str
    repo_path: str
    status: str
    command: str
    stdout_log: str
    stderr_log: str
    input_json: dict
    diff_summary: str
    changed_files: list[str]
    started_at: datetime | None
    finished_at: datetime | None
    result_summary: str

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TestRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workdoc_id: int
    agent_run_id: int
    status: str
    command: str
    stdout_log: str
    stderr_log: str
    exit_code: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

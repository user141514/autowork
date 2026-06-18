from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workdoc_id: int | None
    agent_run_id: int | None
    decision: str
    stage: str
    reasons: list[str]
    metadata_json: dict
    created_at: datetime


class PolicyDecisionResult(BaseModel):
    decision: str
    stage: str
    reasons: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

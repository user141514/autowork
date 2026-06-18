from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCandidateFromSegmentRequest(BaseModel):
    segment_id: int


class TaskCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    segment_id: int
    room_id: str
    command_text: str
    evidence_message_ids: list[int]
    repo_path: str | None
    acceptance_criteria: list[str]
    missing_fields: list[str]
    workdoc_id: int | None
    confidence: str
    status: str
    created_at: datetime


class TaskCandidateUpdateRequest(BaseModel):
    repo_path: str | None = None
    acceptance_criteria: list[str] | None = None

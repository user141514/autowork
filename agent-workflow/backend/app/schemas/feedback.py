from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeedbackRequest(BaseModel):
    room_id: str = "mock-room"
    adapter_type: str = "mock"


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: str
    adapter_type: str
    target_type: str
    target_id: int
    text: str
    status: str
    error_code: str | None
    metadata_json: dict
    created_at: datetime

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BotCommandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    room_id: str
    command_type: str
    command_text: str
    target_workdoc_id: int | None
    status: str
    error_code: str | None
    metadata_json: dict
    created_at: datetime


class BotCommandProcessRequest(BaseModel):
    message_id: int

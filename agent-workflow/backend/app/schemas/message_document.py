from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.demand_radar import CandidateRequirement, DemandMessage


ExtractorMode = Literal["local", "llm", "provided"]


class MessageReviewDocumentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    messages: list[DemandMessage]
    extractor: ExtractorMode = "local"
    title: str | None = None
    write_document: bool = Field(default=False, alias="writeDocument")


class MessageReviewDocumentFromCandidatesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    messages: list[DemandMessage]
    candidates: list[CandidateRequirement]
    title: str | None = None
    write_document: bool = Field(default=False, alias="writeDocument")


class MessageReviewDocumentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    review_document_id: str = Field(alias="reviewDocumentId")
    title: str
    extractor: ExtractorMode
    created_at: datetime = Field(alias="createdAt")
    source_message_count: int = Field(alias="sourceMessageCount")
    candidate_count: int = Field(alias="candidateCount")
    candidates: list[CandidateRequirement]
    markdown: str
    document_path: str | None = Field(default=None, alias="documentPath")
    warnings: list[str] = Field(default_factory=list)

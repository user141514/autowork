from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.context_confidence import ContextAssessment


MessageType = Literal["text", "image", "file", "link", "system", "unknown"]
CandidateStatus = Literal["pending_review", "suspect", "expired"]
Confidence = Literal["low", "medium", "high"]
RequirementType = Literal["bug", "feature", "document", "data", "config", "uncertain"]


class DemandMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    chat_id: str = Field(alias="chatId")
    chat_name: str = Field(alias="chatName")
    sender: str | None = None
    timestamp: datetime
    text: str
    msg_type: MessageType = Field(default="text", alias="msgType")
    source: str = "manual"
    reply_to_message_id: str | None = Field(default=None, alias="replyToMessageId")
    raw: Any | None = None


class EvidenceMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId")
    sender: str | None = None
    timestamp: datetime
    text: str
    role: str


class CandidateFact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str
    message_id: str = Field(alias="messageId")


class CandidateInference(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str
    basis_message_ids: list[str] = Field(alias="basisMessageIds")


class SignalSummary(BaseModel):
    problem: int = 0
    intent: int = 0
    object: int = 0
    constraint: int = 0
    priority: int = 0
    artifact: int = 0
    termination: int = 0


class CandidateRequirement(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    chat_id: str = Field(alias="chatId")
    chat_name: str = Field(alias="chatName")
    title: str
    requirement_type: RequirementType = Field(alias="requirementType")
    status: CandidateStatus
    confidence: Confidence
    confidence_score: float = Field(alias="confidenceScore")
    hypothesis: str
    evidence_message_ids: list[str] = Field(alias="evidenceMessageIds")
    evidence: list[EvidenceMessage]
    facts: list[CandidateFact]
    inferences: list[CandidateInference]
    missing_fields: list[str] = Field(alias="missingFields")
    signal_summary: SignalSummary = Field(alias="signalSummary")
    noise_ratio: float = Field(alias="noiseRatio")
    context_assessment: ContextAssessment | None = Field(default=None, alias="contextAssessment")


class DemandRadarExtractRequest(BaseModel):
    messages: list[DemandMessage]


class DemandRadarExtractResponse(BaseModel):
    candidates: list[CandidateRequirement]

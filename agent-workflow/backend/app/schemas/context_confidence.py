from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ContextResolution = Literal["self_contained", "local_context_enough", "needs_more_history", "needs_user_input"]
SuggestedAction = Literal["direct_answer_ready", "candidate_ready", "keep_scanning", "ask_user", "ignore"]
Confidence = Literal["low", "medium", "high"]


class ContextAssessment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    resolution: ContextResolution
    suggested_action: SuggestedAction = Field(alias="suggestedAction")
    confidence_score: float = Field(alias="confidenceScore")
    confidence: Confidence
    reasons: list[str]
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    evidence_message_ids: list[str] = Field(default_factory=list, alias="evidenceMessageIds")
    suggested_lookback_messages: int = Field(default=0, alias="suggestedLookbackMessages")


class DirectAnswerDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str
    answer_strategy: str = Field(alias="answerStrategy")
    evidence_message_ids: list[str] = Field(alias="evidenceMessageIds")
    status: Literal["draft"] = "draft"


class ContextConfidenceResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assessment: ContextAssessment
    direct_answer_draft: DirectAnswerDraft | None = Field(default=None, alias="directAnswerDraft")

from fastapi import APIRouter

from app.schemas.context_confidence import ContextConfidenceResult
from app.schemas.demand_radar import DemandRadarExtractRequest
from app.services.context_confidence import ContextConfidenceAnalyzer


router = APIRouter(prefix="/context-confidence", tags=["context-confidence"])


@router.post("/analyze", response_model=ContextConfidenceResult, response_model_by_alias=True)
def analyze_context_confidence(request: DemandRadarExtractRequest):
    return ContextConfidenceAnalyzer().analyze(request.messages)

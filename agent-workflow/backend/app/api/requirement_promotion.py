from fastapi import APIRouter, HTTPException

from app.schemas.requirement_promotion import RequirementPromotionRequest, RequirementPromotionResult
from app.services.requirement_promotion.agent_inbox_writer import AgentInboxWriter
from app.services.requirement_promotion.requirement_promoter import RequirementPromoter, RequirementPromotionError


router = APIRouter(prefix="/requirement-promotion", tags=["requirement-promotion"])


@router.post("/promote", response_model=RequirementPromotionResult, response_model_by_alias=True)
def promote_requirement(request: RequirementPromotionRequest):
    try:
        result = RequirementPromoter().promote(request.candidate, request.decision)
    except RequirementPromotionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.write_inbox:
        inbox_path = AgentInboxWriter().write(result)
        result.inbox_path = str(inbox_path)
    return result

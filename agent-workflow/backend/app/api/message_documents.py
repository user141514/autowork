from fastapi import APIRouter, HTTPException

from app.schemas.message_document import MessageReviewDocumentFromCandidatesRequest, MessageReviewDocumentRequest, MessageReviewDocumentResponse
from app.services.llm_client import LLMConfigurationError, LLMRequestError
from app.services.message_document_service import MessageDocumentWriteError, MessageReviewDocumentService


router = APIRouter(prefix="/message-documents", tags=["message-documents"])


@router.post("/from-demand-messages", response_model=MessageReviewDocumentResponse, response_model_by_alias=True)
def create_message_review_document(request: MessageReviewDocumentRequest):
    try:
        return MessageReviewDocumentService().build(request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (LLMRequestError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except MessageDocumentWriteError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/from-candidates", response_model=MessageReviewDocumentResponse, response_model_by_alias=True)
def create_message_review_document_from_candidates(request: MessageReviewDocumentFromCandidatesRequest):
    try:
        return MessageReviewDocumentService().build_from_candidates(
            messages=request.messages,
            candidates=request.candidates,
            title=request.title,
            write_document=request.write_document,
        )
    except MessageDocumentWriteError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

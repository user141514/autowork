from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.feedback import FeedbackRead, FeedbackRequest
from app.services.feedback_service import FeedbackService


router = APIRouter(prefix="/chat-feedback", tags=["chat-feedback"])


@router.post("/task-candidate/{candidate_id}", response_model=FeedbackRead)
def send_task_candidate_feedback(
    candidate_id: int,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
):
    return FeedbackService(db).task_candidate_feedback(candidate_id, request.room_id, request.adapter_type)


@router.post("/workdoc/{workdoc_id}", response_model=FeedbackRead)
def send_workdoc_feedback(workdoc_id: int, request: FeedbackRequest, db: Session = Depends(get_db)):
    return FeedbackService(db).workdoc_feedback(workdoc_id, request.room_id, request.adapter_type)


@router.post("/agent-run/{agent_run_id}", response_model=FeedbackRead)
def send_agent_run_feedback(agent_run_id: int, request: FeedbackRequest, db: Session = Depends(get_db)):
    return FeedbackService(db).agent_run_feedback(agent_run_id, request.room_id, request.adapter_type)


@router.post("/report/{workdoc_id}", response_model=FeedbackRead)
def send_report_feedback(workdoc_id: int, request: FeedbackRequest, db: Session = Depends(get_db)):
    return FeedbackService(db).report_feedback(workdoc_id, request.room_id, request.adapter_type)

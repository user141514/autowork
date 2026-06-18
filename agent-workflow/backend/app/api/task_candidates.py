from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.task_candidate import TaskCandidateFromSegmentRequest, TaskCandidateRead, TaskCandidateUpdateRequest
from app.schemas.workdoc import WorkDocFromTaskCandidateRequest, WorkDocRead
from app.services.task_candidate_service import TaskCandidateService
from app.services.workdoc_service import WorkDocService


router = APIRouter(prefix="/task-candidates", tags=["task-candidates"])


@router.post("/from-segment", response_model=TaskCandidateRead)
def create_task_candidate_from_segment(
    request: TaskCandidateFromSegmentRequest,
    db: Session = Depends(get_db),
):
    return TaskCandidateService(db).create_from_segment(request)


@router.post("/from-segment/{segment_id}", response_model=TaskCandidateRead)
def create_task_candidate_from_segment_path(segment_id: int, db: Session = Depends(get_db)):
    return TaskCandidateService(db).create_from_segment(TaskCandidateFromSegmentRequest(segment_id=segment_id))


@router.get("", response_model=list[TaskCandidateRead])
def list_task_candidates(db: Session = Depends(get_db)):
    return TaskCandidateService(db).list_candidates()


@router.get("/{candidate_id}", response_model=TaskCandidateRead)
def get_task_candidate(candidate_id: int, db: Session = Depends(get_db)):
    return TaskCandidateService(db).get_candidate(candidate_id)


@router.post("/{candidate_id}/update", response_model=TaskCandidateRead)
def update_task_candidate(
    candidate_id: int,
    request: TaskCandidateUpdateRequest,
    db: Session = Depends(get_db),
):
    return TaskCandidateService(db).update_candidate(candidate_id, request)


@router.post("/{candidate_id}/convert-to-workdoc", response_model=WorkDocRead)
def convert_task_candidate_to_workdoc(
    candidate_id: int,
    request: WorkDocFromTaskCandidateRequest | None = None,
    db: Session = Depends(get_db),
):
    payload = request or WorkDocFromTaskCandidateRequest(task_candidate_id=candidate_id)
    payload.task_candidate_id = candidate_id
    workdoc = WorkDocService(db).create_from_task_candidate(payload)
    TaskCandidateService(db).mark_converted(candidate_id, workdoc.id)
    return workdoc

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.workdoc import (
    WorkDocFromMessagesRequest,
    WorkDocFromTaskCandidateRequest,
    WorkDocRead,
    WorkDocUpdateRequest,
    WorkDocValidationResult,
)
from app.services.workdoc_service import WorkDocService
from app.services.task_candidate_service import TaskCandidateService


router = APIRouter(prefix="/workdocs", tags=["workdocs"])


@router.post("/from-messages", response_model=WorkDocRead)
def create_workdoc_from_messages(request: WorkDocFromMessagesRequest, db: Session = Depends(get_db)):
    return WorkDocService(db).create_from_messages(request)


@router.post("/from-task-candidate", response_model=WorkDocRead)
def create_workdoc_from_task_candidate(request: WorkDocFromTaskCandidateRequest, db: Session = Depends(get_db)):
    workdoc = WorkDocService(db).create_from_task_candidate(request)
    TaskCandidateService(db).mark_converted(request.task_candidate_id, workdoc.id)
    return workdoc


@router.get("", response_model=list[WorkDocRead])
def list_workdocs(
    status: str | None = Query(default=None, min_length=1),
    risk_level: str | None = Query(default=None, min_length=1),
    repo_name: str | None = Query(default=None, min_length=1),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return WorkDocService(db).list_workdocs(
        status=status,
        risk_level=risk_level,
        repo_name=repo_name,
        limit=limit,
        offset=offset,
    )


@router.get("/{workdoc_id}", response_model=WorkDocRead)
def get_workdoc(workdoc_id: int = Path(ge=1), db: Session = Depends(get_db)):
    return WorkDocService(db).get_workdoc(workdoc_id)


@router.patch("/{workdoc_id}", response_model=WorkDocRead)
def update_workdoc(
    workdoc_id: int = Path(ge=1),
    request: WorkDocUpdateRequest = Body(...),
    db: Session = Depends(get_db),
):
    return WorkDocService(db).update(workdoc_id, request)


@router.post("/{workdoc_id}/validate", response_model=WorkDocValidationResult)
def validate_workdoc(workdoc_id: int = Path(ge=1), db: Session = Depends(get_db)):
    workdoc, valid, reasons = WorkDocService(db).validate(workdoc_id)
    return WorkDocValidationResult(workdoc=WorkDocRead.model_validate(workdoc), valid=valid, reasons=reasons)


@router.post("/{workdoc_id}/approve", response_model=WorkDocRead)
def approve_workdoc(workdoc_id: int = Path(ge=1), db: Session = Depends(get_db)):
    return WorkDocService(db).approve(workdoc_id)

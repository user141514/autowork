from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.workdoc import WorkDocFromMessagesRequest, WorkDocRead, WorkDocValidationResult
from app.services.workdoc_service import WorkDocService


router = APIRouter(prefix="/workdocs", tags=["workdocs"])


@router.post("/from-messages", response_model=WorkDocRead)
def create_workdoc_from_messages(request: WorkDocFromMessagesRequest, db: Session = Depends(get_db)):
    return WorkDocService(db).create_from_messages(request)


@router.get("", response_model=list[WorkDocRead])
def list_workdocs(db: Session = Depends(get_db)):
    return WorkDocService(db).list_workdocs()


@router.get("/{workdoc_id}", response_model=WorkDocRead)
def get_workdoc(workdoc_id: int, db: Session = Depends(get_db)):
    return WorkDocService(db).get_workdoc(workdoc_id)


@router.post("/{workdoc_id}/validate", response_model=WorkDocValidationResult)
def validate_workdoc(workdoc_id: int, db: Session = Depends(get_db)):
    workdoc, valid, reasons = WorkDocService(db).validate(workdoc_id)
    return WorkDocValidationResult(workdoc=WorkDocRead.model_validate(workdoc), valid=valid, reasons=reasons)


@router.post("/{workdoc_id}/approve", response_model=WorkDocRead)
def approve_workdoc(workdoc_id: int, db: Session = Depends(get_db)):
    return WorkDocService(db).approve(workdoc_id)

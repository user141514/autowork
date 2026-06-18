from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workdoc import WorkDoc
from app.schemas.report import WorkDocReport
from app.services.report_service import ReportService


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/workdoc/{workdoc_id}", response_model=WorkDocReport)
def get_workdoc_report(workdoc_id: int, db: Session = Depends(get_db)):
    report = ReportService(db).workdoc_report(workdoc_id)
    workdoc = db.get(WorkDoc, workdoc_id)
    return WorkDocReport(workdoc_id=workdoc_id, status=workdoc.status if workdoc else "not_found", report=report)


@router.get("/workdoc/{workdoc_id}/markdown", response_class=PlainTextResponse)
def get_workdoc_report_markdown(workdoc_id: int, db: Session = Depends(get_db)):
    return ReportService(db).workdoc_report(workdoc_id)


@router.get("/agent-run/{agent_run_id}", response_class=PlainTextResponse)
def get_agent_run_report(agent_run_id: int, db: Session = Depends(get_db)):
    return ReportService(db).agent_run_report(agent_run_id)

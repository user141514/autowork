from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.test_run import TestRunRead
from app.services.test_runner import TestRunner


router = APIRouter(prefix="/tests", tags=["tests"])


@router.post("/run-for-agent-run/{agent_run_id}", response_model=TestRunRead)
def run_tests_for_agent_run(agent_run_id: int, db: Session = Depends(get_db)):
    return TestRunner(db).run_for_agent_run(agent_run_id)


@router.get("/{test_run_id}", response_model=TestRunRead)
def get_test_run(test_run_id: int, db: Session = Depends(get_db)):
    return TestRunner(db).get_test_run(test_run_id)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.agent_run import AgentRunFromWorkDocRequest, AgentRunRead
from app.services.agent_runner import AgentRunnerService


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.post("/from-workdoc/{workdoc_id}", response_model=AgentRunRead)
def create_agent_run_from_workdoc(
    workdoc_id: int,
    request: AgentRunFromWorkDocRequest | None = None,
    db: Session = Depends(get_db),
):
    return AgentRunnerService(db).run_from_workdoc(workdoc_id, request or AgentRunFromWorkDocRequest())


@router.get("/{agent_run_id}", response_model=AgentRunRead)
def get_agent_run(agent_run_id: int, db: Session = Depends(get_db)):
    return AgentRunnerService(db).get_agent_run(agent_run_id)

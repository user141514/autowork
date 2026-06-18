from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_run import AgentRun
from app.schemas.agent_run import AgentRunFromWorkDocRequest, AgentRunRead
from app.services.agent_runner import AgentRunnerService


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get("", response_model=list[AgentRunRead])
def list_agent_runs(
    workdoc_id: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(AgentRun)
    if workdoc_id is not None:
        stmt = stmt.where(AgentRun.workdoc_id == workdoc_id)
    stmt = stmt.order_by(AgentRun.id.asc())
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


@router.post("/from-workdoc/{workdoc_id}", response_model=AgentRunRead)
def create_agent_run_from_workdoc(
    workdoc_id: int = Path(ge=1),
    request: AgentRunFromWorkDocRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    return AgentRunnerService(db).run_from_workdoc(workdoc_id, request or AgentRunFromWorkDocRequest())


@router.get("/{agent_run_id}", response_model=AgentRunRead)
def get_agent_run(agent_run_id: int = Path(ge=1), db: Session = Depends(get_db)):
    return AgentRunnerService(db).get_agent_run(agent_run_id)

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.policy_decision import PolicyDecision
from app.schemas.policy import PolicyDecisionRead


router = APIRouter(prefix="/policy-decisions", tags=["policy-decisions"])


@router.get("", response_model=list[PolicyDecisionRead])
def list_policy_decisions(
    workdoc_id: int | None = Query(default=None, ge=1),
    agent_run_id: int | None = Query(default=None, ge=1),
    stage: str | None = Query(default=None, min_length=1),
    decision: str | None = Query(default=None, min_length=1),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(PolicyDecision)
    if workdoc_id is not None:
        stmt = stmt.where(PolicyDecision.workdoc_id == workdoc_id)
    if agent_run_id is not None:
        stmt = stmt.where(PolicyDecision.agent_run_id == agent_run_id)
    if stage is not None:
        stmt = stmt.where(PolicyDecision.stage == stage)
    if decision is not None:
        stmt = stmt.where(PolicyDecision.decision == decision)
    stmt = stmt.order_by(PolicyDecision.id.asc())
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))

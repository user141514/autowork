from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.git_operation import GitOperation
from app.schemas.git_operation import GitCommitRequest, GitDiffRead, GitOperationRead
from app.services.git_publisher import GitPublisher


router = APIRouter(prefix="/git", tags=["git"])


@router.get("/operations", response_model=list[GitOperationRead])
def list_git_operations(
    workdoc_id: int | None = Query(default=None, ge=1),
    agent_run_id: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(GitOperation)
    if workdoc_id is not None:
        stmt = stmt.where(GitOperation.workdoc_id == workdoc_id)
    if agent_run_id is not None:
        stmt = stmt.where(GitOperation.agent_run_id == agent_run_id)
    stmt = stmt.order_by(GitOperation.id.asc())
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


@router.post("/diff/{agent_run_id}", response_model=GitDiffRead)
def diff_for_run(agent_run_id: int = Path(ge=1), db: Session = Depends(get_db)):
    return GitPublisher(db).diff_for_run(agent_run_id)


@router.post("/branch-from-run/{agent_run_id}", response_model=GitOperationRead)
def branch_from_run(
    agent_run_id: int = Path(ge=1),
    request: GitCommitRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    return GitPublisher(db).branch_from_run(agent_run_id, request or GitCommitRequest())


@router.post("/commit-from-run/{agent_run_id}", response_model=GitOperationRead)
def commit_from_run(
    agent_run_id: int = Path(ge=1),
    request: GitCommitRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    return GitPublisher(db).commit_from_run(agent_run_id, request or GitCommitRequest())


@router.post("/push/{git_operation_id}", response_model=GitOperationRead)
def push(git_operation_id: int = Path(ge=1), db: Session = Depends(get_db)):
    return GitPublisher(db).push(git_operation_id)


@router.post("/create-pr/{git_operation_id}", response_model=GitOperationRead)
def create_pr(git_operation_id: int = Path(ge=1), db: Session = Depends(get_db)):
    return GitPublisher(db).create_pr(git_operation_id)

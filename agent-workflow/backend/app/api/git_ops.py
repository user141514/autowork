from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.git_operation import GitCommitRequest, GitDiffRead, GitOperationRead
from app.services.git_publisher import GitPublisher


router = APIRouter(prefix="/git", tags=["git"])


@router.post("/diff/{agent_run_id}", response_model=GitDiffRead)
def diff_for_run(agent_run_id: int, db: Session = Depends(get_db)):
    return GitPublisher(db).diff_for_run(agent_run_id)


@router.post("/branch-from-run/{agent_run_id}", response_model=GitOperationRead)
def branch_from_run(
    agent_run_id: int,
    request: GitCommitRequest | None = None,
    db: Session = Depends(get_db),
):
    return GitPublisher(db).branch_from_run(agent_run_id, request or GitCommitRequest())


@router.post("/commit-from-run/{agent_run_id}", response_model=GitOperationRead)
def commit_from_run(
    agent_run_id: int,
    request: GitCommitRequest | None = None,
    db: Session = Depends(get_db),
):
    return GitPublisher(db).commit_from_run(agent_run_id, request or GitCommitRequest())


@router.post("/push/{git_operation_id}", response_model=GitOperationRead)
def push(git_operation_id: int, db: Session = Depends(get_db)):
    return GitPublisher(db).push(git_operation_id)


@router.post("/create-pr/{git_operation_id}", response_model=GitOperationRead)
def create_pr(git_operation_id: int, db: Session = Depends(get_db)):
    return GitPublisher(db).create_pr(git_operation_id)

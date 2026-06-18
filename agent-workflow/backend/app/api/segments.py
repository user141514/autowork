from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.segment import MessageSegmentRead, SegmentFromCommandRequest, SegmentFromMessagesRequest
from app.services.segment_service import SegmentService


router = APIRouter(prefix="/segments", tags=["segments"])


@router.post("/from-messages", response_model=MessageSegmentRead)
def create_segment_from_messages(request: SegmentFromMessagesRequest, db: Session = Depends(get_db)):
    return SegmentService(db).create_from_messages(request)


@router.post("/from-command/{message_id}", response_model=MessageSegmentRead)
def create_segment_from_command(
    message_id: int,
    request: SegmentFromCommandRequest | None = None,
    db: Session = Depends(get_db),
):
    return SegmentService(db).create_from_command(
        message_id,
        context_window_size=request.context_window_size if request else None,
    )


@router.get("", response_model=list[MessageSegmentRead])
def list_segments(db: Session = Depends(get_db)):
    return SegmentService(db).list_segments()


@router.get("/{segment_id}", response_model=MessageSegmentRead)
def get_segment(segment_id: int, db: Session = Depends(get_db)):
    return SegmentService(db).get_segment(segment_id)

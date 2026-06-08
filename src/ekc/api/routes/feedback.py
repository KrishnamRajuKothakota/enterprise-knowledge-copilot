"""POST /api/v1/feedback"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.ekc.db.session import get_db
from src.ekc.db.models import User, Feedback, FeedbackRating, QueryLog
from src.ekc.api.deps import get_current_user

router = APIRouter()


class FeedbackRequest(BaseModel):
    query_id: str
    session_id: str
    rating: str          # "up" or "down"
    comment: str | None = None


@router.post("/feedback", status_code=201)
def submit_feedback(
    req: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify query exists
    query_log = db.query(QueryLog).filter(
        QueryLog.query_id == req.query_id
    ).first()
    if not query_log:
        raise HTTPException(status_code=404, detail="Query not found")

    # Check if feedback already exists
    existing = db.query(Feedback).filter(
        Feedback.query_id == req.query_id
    ).first()
    if existing:
        existing.rating = FeedbackRating(req.rating)
        existing.comment = req.comment
        db.commit()
        return {"status": "updated", "feedback_id": existing.feedback_id}

    feedback = Feedback(
        feedback_id=str(uuid.uuid4()),
        query_id=req.query_id,
        user_id=current_user.user_id,
        rating=FeedbackRating(req.rating),
        comment=req.comment,
    )
    db.add(feedback)
    db.commit()
    return {"status": "created", "feedback_id": feedback.feedback_id}
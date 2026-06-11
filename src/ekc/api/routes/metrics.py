"""GET /api/v1/metrics — admin only."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.ekc.db.session import get_db
from src.ekc.db.models import (
    User, QueryLog, Feedback, RagasEvaluation,
    Document, Chunk as ChunkModel
)
from src.ekc.api.deps import require_admin
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/metrics")
def get_metrics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Query stats — last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    total_queries_7d = db.query(QueryLog).filter(
        QueryLog.created_at >= seven_days_ago
    ).count()

    avg_latency = db.query(func.avg(QueryLog.latency_ms)).filter(
        QueryLog.created_at >= seven_days_ago,
        QueryLog.latency_ms.isnot(None),
    ).scalar() or 0

    cache_hits = db.query(QueryLog).filter(
        QueryLog.created_at >= seven_days_ago,
        QueryLog.cache_hit == True,
    ).count()

    cache_hit_rate = (cache_hits / total_queries_7d) if total_queries_7d > 0 else 0

    fallback_count = db.query(QueryLog).filter(
        QueryLog.created_at >= seven_days_ago,
        QueryLog.status == "fallback",
    ).count()

    # Feedback stats
    thumbs_up = db.query(Feedback).filter(
        Feedback.rating == "up"
    ).count()
    thumbs_down = db.query(Feedback).filter(
        Feedback.rating == "down"
    ).count()

    # Latest RAGAS evaluation
    latest_ragas = db.query(RagasEvaluation).order_by(
        RagasEvaluation.run_date.desc()
    ).first()

    # LLM judge stats
    scored_feedback = db.query(Feedback).filter(
        Feedback.llm_judge_score.isnot(None)
    ).count()
    avg_judge_score = db.query(func.avg(Feedback.llm_judge_score)).filter(
        Feedback.llm_judge_score.isnot(None)
    ).scalar() or 0

    # Recent scored feedback for dashboard table
    from src.ekc.db.models import QueryLog as QL
    recent_scored = db.query(Feedback, QL).join(
        QL, Feedback.query_id == QL.query_id
    ).filter(
        Feedback.llm_judge_score.isnot(None)
    ).order_by(Feedback.created_at.desc()).limit(10).all()

    recent_list = []
    for fb, ql in recent_scored:
        recent_list.append({
            "query": ql.query_text[:60],
            "rating": fb.rating.value,
            "score": round(fb.llm_judge_score, 3),
        })

    # Corpus stats
    total_docs = db.query(Document).count()
    total_chunks = db.query(ChunkModel).count()

    return {
        "queries": {
            "total_7d": total_queries_7d,
            "avg_latency_ms": round(avg_latency),
            "cache_hit_rate": round(cache_hit_rate, 3),
            "fallback_count": fallback_count,
        },
        "feedback": {
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "total": thumbs_up + thumbs_down,
        },
        "ragas": {
            "faithfulness": latest_ragas.faithfulness if latest_ragas else None,
            "context_precision": latest_ragas.context_precision if latest_ragas else None,
            "answer_relevancy": latest_ragas.answer_relevancy if latest_ragas else None,
            "run_date": latest_ragas.run_date.isoformat() if latest_ragas else None,
        },
        "llm_judge": {
            "avg_score": round(avg_judge_score, 3),
            "scored_count": scored_feedback,
            "recent": recent_list,
        },
        "corpus": {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
        },
    }
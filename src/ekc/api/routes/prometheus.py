"""
Prometheus metrics endpoint — GET /metrics
Exposes system health, query stats, RAGAS scores, cache performance.
"""
import logging
from fastapi import APIRouter, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.ekc.db.session import SessionLocal
from src.ekc.db.models import QueryLog, Feedback, RagasEvaluation, Chunk as ChunkModel, Document
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()


def collect_metrics(db: Session) -> dict:
    """Collect all metrics from DB."""
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    one_day_ago = datetime.utcnow() - timedelta(days=1)

    # Query metrics
    total_queries_7d = db.query(QueryLog).filter(
        QueryLog.created_at >= seven_days_ago
    ).count()

    total_queries_24h = db.query(QueryLog).filter(
        QueryLog.created_at >= one_day_ago
    ).count()

    avg_latency = db.query(func.avg(QueryLog.latency_ms)).filter(
        QueryLog.created_at >= seven_days_ago,
        QueryLog.latency_ms.isnot(None),
    ).scalar() or 0

    cache_hits_7d = db.query(QueryLog).filter(
        QueryLog.created_at >= seven_days_ago,
        QueryLog.cache_hit == True,
    ).count()

    cache_hit_rate = (cache_hits_7d / total_queries_7d) if total_queries_7d > 0 else 0

    fallback_count = db.query(QueryLog).filter(
        QueryLog.created_at >= seven_days_ago,
        QueryLog.status == "fallback",
    ).count()

    # Feedback metrics
    thumbs_up = db.query(Feedback).filter(
        Feedback.rating == "up"
    ).count()
    thumbs_down = db.query(Feedback).filter(
        Feedback.rating == "down"
    ).count()

    avg_judge_score = db.query(func.avg(Feedback.llm_judge_score)).filter(
        Feedback.llm_judge_score.isnot(None)
    ).scalar() or 0

    # RAGAS metrics
    latest_ragas = db.query(RagasEvaluation).order_by(
        RagasEvaluation.run_date.desc()
    ).first()

    # Corpus metrics
    total_docs = db.query(Document).count()
    total_chunks = db.query(ChunkModel).count()

    return {
        "total_queries_7d": total_queries_7d,
        "total_queries_24h": total_queries_24h,
        "avg_latency_ms": round(avg_latency, 2),
        "cache_hit_rate": round(cache_hit_rate, 4),
        "fallback_count_7d": fallback_count,
        "thumbs_up_total": thumbs_up,
        "thumbs_down_total": thumbs_down,
        "avg_judge_score": round(avg_judge_score, 4),
        "ragas_faithfulness": latest_ragas.faithfulness if latest_ragas else 0,
        "ragas_context_precision": latest_ragas.context_precision if latest_ragas else 0,
        "ragas_answer_relevancy": latest_ragas.answer_relevancy if latest_ragas else 0,
        "ragas_context_recall": latest_ragas.context_recall if latest_ragas else 0,
        "total_documents": total_docs,
        "total_chunks": total_chunks,
    }


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Prometheus-format metrics endpoint."""
    db = SessionLocal()
    try:
        m = collect_metrics(db)

        lines = [
            "# HELP ekc_queries_total Total queries in last 7 days",
            "# TYPE ekc_queries_total gauge",
            f'ekc_queries_total{{window="7d"}} {m["total_queries_7d"]}',
            f'ekc_queries_total{{window="24h"}} {m["total_queries_24h"]}',
            "",
            "# HELP ekc_latency_ms_avg Average query latency in milliseconds",
            "# TYPE ekc_latency_ms_avg gauge",
            f'ekc_latency_ms_avg {m["avg_latency_ms"]}',
            "",
            "# HELP ekc_cache_hit_rate Cache hit rate (0-1)",
            "# TYPE ekc_cache_hit_rate gauge",
            f'ekc_cache_hit_rate {m["cache_hit_rate"]}',
            "",
            "# HELP ekc_fallback_count Fallback responses in last 7 days",
            "# TYPE ekc_fallback_count gauge",
            f'ekc_fallback_count {m["fallback_count_7d"]}',
            "",
            "# HELP ekc_feedback_total User feedback counts",
            "# TYPE ekc_feedback_total gauge",
            f'ekc_feedback_total{{rating="up"}} {m["thumbs_up_total"]}',
            f'ekc_feedback_total{{rating="down"}} {m["thumbs_down_total"]}',
            "",
            "# HELP ekc_llm_judge_score_avg Average LLM judge score",
            "# TYPE ekc_llm_judge_score_avg gauge",
            f'ekc_llm_judge_score_avg {m["avg_judge_score"]}',
            "",
            "# HELP ekc_ragas_score RAGAS evaluation scores",
            "# TYPE ekc_ragas_score gauge",
            f'ekc_ragas_score{{metric="faithfulness"}} {m["ragas_faithfulness"]}',
            f'ekc_ragas_score{{metric="context_precision"}} {m["ragas_context_precision"]}',
            f'ekc_ragas_score{{metric="answer_relevancy"}} {m["ragas_answer_relevancy"]}',
            f'ekc_ragas_score{{metric="context_recall"}} {m["ragas_context_recall"]}',
            "",
            "# HELP ekc_corpus_size Knowledge corpus size",
            "# TYPE ekc_corpus_size gauge",
            f'ekc_corpus_size{{type="documents"}} {m["total_documents"]}',
            f'ekc_corpus_size{{type="chunks"}} {m["total_chunks"]}',
            "",
        ]

        return Response(
            content="\n".join(lines),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    finally:
        db.close()
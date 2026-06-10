"""
Celery tasks for async document ingestion and LLM judge batch.
"""
import logging
from src.ekc.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="src.ekc.tasks.ingest_tasks.ingest_document_task",
    max_retries=3,
    default_retry_delay=60,
)
def ingest_document_task(
    self,
    file_path: str,
    namespace: str = "general",
    access_roles: list = None,
):
    """
    Async document ingestion task.
    Called by POST /api/v1/ingest when async=true.
    """
    if access_roles is None:
        access_roles = ["admin", "junior_engineer", "l1_support", "lead"]

    logger.info(f"Starting ingestion: {file_path} -> {namespace}")

    try:
        from src.ekc.ingestion.pipeline import DocumentIngestionPipeline
        pipeline = DocumentIngestionPipeline()
        result = pipeline.ingest_file(
            file_path,
            namespace=namespace,
            access_roles=access_roles,
        )
        logger.info(
            f"Ingestion complete: {file_path} -> "
            f"{result.chunks_created} chunks, "
            f"{result.pii_redactions} PII redactions"
        )
        return {
            "status": "completed",
            "file_path": file_path,
            "chunks_created": result.chunks_created,
            "embeddings_created": result.embeddings_created,
            "pii_redactions": result.pii_redactions,
            "errors": result.errors,
        }

    except Exception as exc:
        logger.error(f"Ingestion failed: {file_path} — {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="src.ekc.tasks.ingest_tasks.llm_judge_task",
    max_retries=2,
)
def llm_judge_task(limit: int = 50):
    """
    Nightly LLM-as-judge scoring batch.
    Scheduled via Celery Beat or cron.
    """
    logger.info("Starting LLM judge batch task...")
    try:
        from src.ekc.db.session import SessionLocal
        from src.ekc.db.models import Feedback, QueryLog
        from src.ekc.llm.client import get_llm_client

        db = SessionLocal()
        llm = get_llm_client()

        unscored = db.query(Feedback, QueryLog).join(
            QueryLog, Feedback.query_id == QueryLog.query_id
        ).filter(
            Feedback.llm_judge_score.is_(None),
            QueryLog.response_text.isnot(None),
            QueryLog.status != "fallback",
        ).limit(limit).all()

        logger.info(f"Found {len(unscored)} unscored entries")

        scored = 0
        for feedback, query_log in unscored:
            try:
                from scripts.llm_judge_batch import score_response
                score = score_response(
                    llm,
                    query_log.query_text,
                    query_log.response_text or "",
                    f"Retrieved {len(query_log.retrieved_chunk_ids or [])} chunks",
                )
                if score is not None:
                    feedback.llm_judge_score = score
                    scored += 1
            except Exception as e:
                logger.warning(f"Score failed: {e}")

        db.commit()
        db.close()
        logger.info(f"LLM judge batch complete: {scored}/{len(unscored)} scored")
        return {"scored": scored, "total": len(unscored)}

    except Exception as exc:
        logger.error(f"LLM judge task failed: {exc}")
        raise

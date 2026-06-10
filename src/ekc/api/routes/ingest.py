"""POST /api/v1/ingest — admin only. Supports sync and async modes."""
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from src.ekc.db.models import User
from src.ekc.api.deps import require_admin
from src.ekc.ingestion.pipeline import DocumentIngestionPipeline

router = APIRouter()


class IngestRequest(BaseModel):
    file_path: str
    namespace: str = "general"
    access_roles: list[str] = ["junior_engineer", "l1_support", "lead", "admin"]
    async_mode: bool = True


@router.post("/ingest", status_code=202)
def ingest_document(
    req: IngestRequest,
    admin: User = Depends(require_admin),
):
    if not os.path.exists(req.file_path):
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {req.file_path}"
        )

    job_id = str(uuid.uuid4())

    if req.async_mode:
        # Async via Celery
        try:
            from src.ekc.tasks.ingest_tasks import ingest_document_task
            task = ingest_document_task.apply_async(
                args=[req.file_path],
                kwargs={
                    "namespace": req.namespace,
                    "access_roles": req.access_roles,
                },
                task_id=job_id,
                queue="ingestion",
            )
            return {
                "job_id": job_id,
                "status": "queued",
                "mode": "async",
                "message": f"Ingestion queued. Poll /api/v1/ingest/{job_id} for status.",
            }
        except Exception as e:
            # Celery not available — fall back to sync
            pass

    # Synchronous fallback
    pipeline = DocumentIngestionPipeline()
    result = pipeline.ingest_file(
        req.file_path,
        namespace=req.namespace,
        access_roles=req.access_roles,
    )

    if result.files_failed > 0:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {result.errors}"
        )

    return {
        "job_id": job_id,
        "status": "completed",
        "mode": "sync",
        "chunks_created": result.chunks_created,
        "embeddings_created": result.embeddings_created,
        "pii_redactions": result.pii_redactions,
        "errors": result.errors,
    }


@router.get("/ingest/{job_id}")
def get_ingest_status(
    job_id: str,
    admin: User = Depends(require_admin),
):
    """Check status of an async ingestion job."""
    try:
        from src.ekc.celery_app import celery_app
        from celery.result import AsyncResult
        result = AsyncResult(job_id, app=celery_app)
        return {
            "job_id": job_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }
    except Exception as e:
        return {"job_id": job_id, "status": "unknown", "error": str(e)}

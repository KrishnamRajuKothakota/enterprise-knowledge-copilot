"""POST /api/v1/ingest — admin only."""
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.ekc.db.models import User
from src.ekc.api.deps import require_admin
from src.ekc.ingestion.pipeline import DocumentIngestionPipeline

router = APIRouter()


class IngestRequest(BaseModel):
    file_path: str
    namespace: str = "general"
    access_roles: list[str] = ["junior_engineer", "l1_support", "lead", "admin"]


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

    # For the hackathon: synchronous ingestion
    # Production: Celery async task
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
        "chunks_created": result.chunks_created,
        "embeddings_created": result.embeddings_created,
        "pii_redactions": result.pii_redactions,
        "errors": result.errors,
    }
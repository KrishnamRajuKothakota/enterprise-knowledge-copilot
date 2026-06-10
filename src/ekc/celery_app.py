"""
Celery application — async task queue for document ingestion.
Broker: Redis. Backend: Redis.
"""
from celery import Celery
from src.ekc.core.config import settings

celery_app = Celery(
    "ekc",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.ekc.tasks.ingest_tasks"],
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "src.ekc.tasks.ingest_tasks.ingest_document_task": {"queue": "ingestion"},
        "src.ekc.tasks.ingest_tasks.llm_judge_task": {"queue": "evaluation"},
    },
)

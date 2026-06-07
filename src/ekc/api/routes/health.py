from fastapi import APIRouter
from sqlalchemy import text
import redis as redis_client
import httpx
from src.ekc.db.session import SessionLocal
from src.ekc.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    status = {"status": "ok", "checks": {}}

    # Postgres
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status["checks"]["postgres"] = "ok"
    except Exception as e:
        status["checks"]["postgres"] = f"error: {e}"
        status["status"] = "degraded"

    # Redis
    try:
        r = redis_client.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        status["checks"]["redis"] = "ok"
    except Exception as e:
        status["checks"]["redis"] = f"error: {e}"
        status["status"] = "degraded"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
        models = [m["name"] for m in resp.json().get("models", [])]
        if settings.ollama_model in models:
            status["checks"]["ollama"] = f"ok ({settings.ollama_model} loaded)"
        else:
            status["checks"]["ollama"] = f"model {settings.ollama_model} not found"
            status["status"] = "degraded"
    except Exception as e:
        status["checks"]["ollama"] = f"error: {e}"
        status["status"] = "degraded"

    return status
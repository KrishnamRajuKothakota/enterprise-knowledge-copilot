"""
Enterprise Knowledge Copilot — FastAPI application entry point.
Includes: rate limiting, CORS, all routers, startup warmup.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.ekc.core.config import settings
from src.ekc.api.routes import health, auth, query, feedback, metrics, ingest, prometheus

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# App
from fastapi.responses import JSONResponse
import json as _json

class UnicodeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return _json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(',', ':'),
        ).encode('utf-8')

app = FastAPI(
    default_response_class=UnicodeJSONResponse,
    title="Enterprise Knowledge Copilot",
    description="Multi-agent RAG system with triple-fusion retrieval",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "https://localhost",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Routers
app.include_router(health.router,     tags=["System"])
app.include_router(auth.router,       prefix="/api/v1", tags=["Auth"])
app.include_router(query.router,      prefix="/api/v1", tags=["Query"])
app.include_router(feedback.router,   prefix="/api/v1", tags=["Feedback"])
app.include_router(metrics.router,    prefix="/api/v1", tags=["Metrics"])
app.include_router(ingest.router,     prefix="/api/v1", tags=["Ingest"])
app.include_router(prometheus.router, tags=["Observability"])

@app.on_event("startup")
async def startup():
    print(f"EKC starting — env={settings.app_env}, "
          f"ollama={settings.ollama_base_url}, "
          f"model={settings.ollama_model}")
    import httpx
    try:
        print("Warming up Ollama...")
        httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "options": {"num_predict": 5},
                "messages": [{"role": "user", "content": "/no_think say ready"}],
            },
            timeout=60,
        )
        print("Ollama warmed up")
    except Exception as e:
        print(f"Ollama warmup failed: {e}")

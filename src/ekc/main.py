from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.ekc.api.routes import health, auth
from src.ekc.core.config import settings

from src.ekc.api.routes import health, auth, query

from src.ekc.api.routes import health, auth, query, feedback, metrics, ingest, prometheus


app = FastAPI(
    title="Enterprise Knowledge Copilot",
    description="Multi-agent RAG system with triple-fusion retrieval",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["System"])
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])

# add after the existing include_router lines:
app.include_router(query.router, prefix="/api/v1", tags=["Query"])


app.include_router(query.router,    prefix="/api/v1", tags=["Query"])
app.include_router(feedback.router, prefix="/api/v1", tags=["Feedback"])
app.include_router(metrics.router,  prefix="/api/v1", tags=["Metrics"])
app.include_router(ingest.router,   prefix="/api/v1", tags=["Ingest"])

app.include_router(prometheus.router, tags=["Observability"])


@app.on_event("startup")
async def startup():
    print(f"EKC starting — env={settings.app_env}, "
          f"ollama={settings.ollama_base_url}, "
          f"model={settings.ollama_model}")
    # Warm up Ollama on startup
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
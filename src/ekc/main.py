from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.ekc.api.routes import health, auth
from src.ekc.core.config import settings

from src.ekc.api.routes import health, auth, query


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


@app.on_event("startup")
async def startup():
    print(f"EKC starting — env={settings.app_env}, "
          f"ollama={settings.ollama_base_url}, "
          f"model={settings.ollama_model}")
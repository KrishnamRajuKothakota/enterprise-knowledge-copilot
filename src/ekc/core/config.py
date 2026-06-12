from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    ollama_base_url: str = "http://172.16.29.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout: int = 90
    ollama_keep_alive: str = "-1"

    # Database
    database_url: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ekc_db"
    postgres_user: str = "ekc_user"
    postgres_password: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    jwt_expire_minutes: int = 1440  # alias for compatibility

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    log_retention_months: int = 12

    # Ingestion
    chunk_size: int = 512
    chunk_overlap: int = 50
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Retrieval
    vector_top_k: int = 5
    bm25_top_k: int = 5
    graph_top_k: int = 5
    rerank_top_n: int = 15
    final_top_k: int = 5
    confidence_threshold: float = 0.7

    # Paths
    data_dir: str = "data"
    faiss_index_path: str = "data/indexes/faiss.index"
    bm25_index_path: str = "data/indexes/bm25.pkl"
    graph_path: str = "data/indexes/graph.graphml"

    # RAGAS thresholds
    ragas_faithfulness_threshold: float = 0.85
    ragas_context_precision_threshold: float = 0.80


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
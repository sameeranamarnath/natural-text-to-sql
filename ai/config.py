"""Runtime configuration for the SQL agent service.

Every value is environment-overridable, so the same image runs against a local
vLLM container or any hosted OpenAI-compatible endpoint.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # vLLM exposes an OpenAI-compatible API, so we point the OpenAI client at it.
    llm_base_url: str = "http://vllm:8000/v1"
    llm_api_key: str = "local-vllm"
    llm_model: str = "Qwen/Qwen3-32B"
    llm_temperature: float = 0.0

    # Embeddings. Can be the same vLLM instance or a dedicated one.
    embed_base_url: str = "http://vllm:8000/v1"
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024

    # Vector store for schema chunks and worked examples.
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "sql_schema_chunks"

    # Target database the agent is allowed to query.
    database_url: str = "sqlite:///imdb-movie.sqlite"
    row_limit: int = 50

    # How many times the graph may feed a failed query back for repair.
    max_repair_attempts: int = 3
    retrieval_top_k: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()

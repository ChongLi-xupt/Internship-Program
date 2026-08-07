"""
Application configuration via environment variables.
Uses pydantic-settings for type-safe env loading.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === Application ===
    app_name: str = "rag-smart-query"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # === Database ===
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rag_smart_query"

    # === Redis ===
    redis_url: str = "redis://localhost:6379/0"

    # === Vector Store ===
    vector_store: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_prefix: str = "kb_"
    embedding_dimensions: int = 1536

    # === LLM ===
    # openai | deepseek | anthropic | ollama
    llm_provider: str = "openai"

    # -- OpenAI / OpenAI-compatible --
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_light_model: str = "gpt-4o-mini"

    # -- DeepSeek (OpenAI-compatible protocol) --
    # NOTE: DeepSeek provides NO embedding endpoint. Embeddings must be
    # configured separately via EMBEDDING_* settings below.
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    # deepseek-chat (V3, fast) | deepseek-reasoner (R1, slow, high-latency)
    deepseek_model: str = "deepseek-chat"
    # Light model for cheap tasks (intent classification, query rewrite)
    deepseek_light_model: str = "deepseek-chat"

    # -- Anthropic --
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # -- Ollama (local / air-gapped) --
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # === Embedding (INDEPENDENT from LLM provider) ===
    # openai | huggingface | ollama
    #   openai       — OpenAI or any compatible endpoint (SiliconFlow,
    #                  DashScope compatible-mode, Zhipu, local vLLM/Xinference)
    #   huggingface  — local sentence-transformers model, fully offline, no API cost
    #   ollama       — local Ollama server
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    # Leave blank to fall back to openai_api_key / openai_base_url.
    # Set these when the embedding service differs from the chat service
    # (mandatory when LLM_PROVIDER=deepseek).
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    # Some providers (BGE, Ollama) reject the OpenAI `dimensions` parameter.
    embedding_send_dimensions: bool = True
    embedding_batch_size: int = 32

    # -- Local HuggingFace / sentence-transformers embedding --
    # Model id (resolved from the local HF cache) or an absolute path to a
    # model directory. Blank => reuse `embedding_model`.
    hf_embedding_model: str = ""
    # cpu | cuda | cuda:0 | mps.  Blank => auto-detect (cuda if available).
    hf_embedding_device: str = ""
    # Cosine similarity requires unit-length vectors. Keep True unless the
    # vector store is configured for raw dot-product / L2 distance.
    hf_embedding_normalize: bool = True
    # BGE-family models expect an instruction prefix on the QUERY side only
    # (documents are embedded raw). Omitting it measurably hurts recall on
    # short Chinese queries. Set to "" to disable for non-BGE models.
    hf_embedding_query_instruction: str = "为这个句子生成表示以用于检索相关文章："
    # Never reach out to huggingface.co at runtime — fail loudly instead of
    # silently hanging when the model is missing from the local cache.
    hf_embedding_offline: bool = True
    # Cap torch intra-op threads. 0 => leave torch's default (all cores),
    # which can starve the web workers under concurrent load.
    hf_embedding_torch_threads: int = 0

    # === Security ===
    encryption_key: str = Field(
        default="a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890",
        description="32-byte hex string for AES-256-GCM encryption",
    )
    cors_origins: List[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    # === Storage ===
    storage_type: str = "local"  # local | s3 | minio
    local_storage_path: str = "./data/files"
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "rag-files"

    # === Rate Limits ===
    rate_limit_chat_per_minute: int = 60
    rate_limit_upload_per_hour: int = 20
    rate_limit_sql_per_hour: int = 300
    max_concurrent_query_per_user: int = 3

    # === SQL Guard ===
    sql_guard_max_rows: int = 10000
    sql_guard_timeout_seconds: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

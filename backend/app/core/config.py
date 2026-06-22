"""Application configuration loaded from environment via pydantic-settings."""
from __future__ import annotations

import re
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings. Values come from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "Industrial Knowledge Brain"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,https://indusmind-1.vercel.app,https://*.vercel.app"

    # ---- Auth ----
    auth_enabled: bool = True

    # ---- Supabase ----
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_bucket: str = "documents"

    # ---- Database ----
    database_url: str = ""

    # ---- Gemini ----
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # ---- Embeddings ----
    # The pgvector column is fixed to embedding_dim, so changing the dimension
    # requires a schema change + re-index. Gemini (gemini-embedding-001) and
    # HF BAAI/bge-base-en-v1.5 both produce 768-d vectors.
    embedding_provider: str = "gemini"  # "gemini" | "huggingface" | "mock"
    embedding_dim: int = 768

    # Hugging Face Inference API (HTTP; serverless/Vercel-friendly, no torch)
    hf_api_token: str = ""
    hf_embedding_model: str = "BAAI/bge-base-en-v1.5"

    # Embeddings are generated in batches to cut round-trips during ingestion.
    embedding_batch_size: int = 64

    # ---- Chunking / retrieval ----
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 10

    # ---- OCR ----
    enable_ocr: bool = False

    # ---- Knowledge graph ----
    # Extract industrial entities/relationships (equipment, failures, inspections,
    # maintenance) during ingestion and store them for equipment-history queries.
    # Requires Gemini. Chars of document text fed to the extractor per document.
    enable_kg: bool = True
    kg_extract_max_chars: int = 16000

    @property
    def cors_origins_list(self) -> list[str]:
        """Exact CORS origins (entries without a wildcard).

        Wildcard entries (e.g. ``https://*.vercel.app``) are not valid exact
        origins for Starlette's CORSMiddleware ``allow_origins`` — they are
        handled by :attr:`cors_origin_regex` instead.
        """
        return [
            o.strip()
            for o in self.cors_origins.split(",")
            if o.strip() and "*" not in o
        ]

    @property
    def cors_origin_regex(self) -> str | None:
        """Build a regex matching any wildcard CORS entries.

        Converts e.g. ``https://*.vercel.app`` to
        ``https://[A-Za-z0-9-]+\\.vercel\\.app`` so Vercel preview deployments
        (which get random subdomains) pass CORS. Returns None when there are no
        wildcard entries.
        """
        patterns: list[str] = []
        for raw in self.cors_origins.split(","):
            entry = raw.strip()
            if not entry or "*" not in entry:
                continue
            escaped = re.escape(entry).replace(r"\*", r"[A-Za-z0-9-]+")
            patterns.append(escaped)
        if not patterns:
            return None
        return "|".join(f"(?:{p})" for p in patterns)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_hf(self) -> bool:
        return bool(self.hf_api_token)

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def has_database(self) -> bool:
        return bool(self.database_url)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (single instance per process)."""
    return Settings()


settings = get_settings()

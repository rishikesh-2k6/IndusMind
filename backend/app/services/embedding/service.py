"""Embedding generation with caching and retry.

Vercel-friendly: Gemini embeddings only (no torch / sentence-transformers). When
no Gemini key is configured, a deterministic hash-based mock embedding is used so
the system still runs locally and in tests. Mock vectors are low quality but keep
the full pipeline exercisable offline.

Gemini text-embedding-004 returns 768-dim vectors, matching the pgvector column.
"""
from __future__ import annotations

import asyncio
import hashlib
import math

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger
from app.services.embedding.cache import EmbeddingCache

logger = get_logger(__name__)


class EmbeddingService:
    """Generates embeddings for single texts or batches, with an LRU cache."""

    def __init__(self) -> None:
        self._dim = settings.embedding_dim
        self._cache = EmbeddingCache()
        self._provider = "gemini" if settings.has_gemini else "mock"
        if self._provider == "mock":
            logger.warning(
                "GEMINI_API_KEY not set; EmbeddingService using deterministic mock "
                "embeddings (set the key for real retrieval quality)"
            )
        else:
            logger.info("EmbeddingService provider: gemini (%d dims)", self._dim)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def dim(self) -> int:
        return self._dim

    async def generate_embedding(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = (await self._embed_batch([text]))[0]
        self._cache.set(text, vector)
        return vector

    async def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        results: list[list[float] | None] = [self._cache.get(t) for t in texts]
        missing_idx = [i for i, v in enumerate(results) if v is None]
        if missing_idx:
            to_embed = [texts[i] for i in missing_idx]
            vectors = await self._embed_batch(to_embed)
            for i, vec in zip(missing_idx, vectors):
                results[i] = vec
                self._cache.set(texts[i], vec)
        return [v for v in results if v is not None]

    # ------------------------------------------------------------------ #
    # Providers
    # ------------------------------------------------------------------ #

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            if self._provider == "gemini":
                return await self._embed_gemini(texts)
            return [self._mock_embedding(t) for t in texts]
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(f"Embedding failed: {exc}") from exc

    async def _embed_gemini(self, texts: list[str]) -> list[list[float]]:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)

        def _run() -> list[list[float]]:
            out: list[list[float]] = []
            for text in texts:
                resp = genai.embed_content(
                    model=settings.gemini_embedding_model,
                    content=text,
                    task_type="retrieval_document",
                )
                out.append(resp["embedding"])
            return out

        return await asyncio.to_thread(_run)

    def _mock_embedding(self, text: str) -> list[float]:
        """Deterministic pseudo-embedding from a hash, L2-normalised."""
        vec: list[float] = []
        counter = 0
        while len(vec) < self._dim:
            digest = hashlib.sha256(f"{text}|{counter}".encode("utf-8")).digest()
            for b in digest:
                vec.append((b / 255.0) * 2.0 - 1.0)  # map byte -> [-1, 1]
                if len(vec) >= self._dim:
                    break
            counter += 1
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

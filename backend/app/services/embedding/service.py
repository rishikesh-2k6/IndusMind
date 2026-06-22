"""Embedding generation with caching and retry.

Vercel-friendly: all providers are HTTP-based (no torch / sentence-transformers
bundled). Providers:
  - gemini       -> Gemini Embeddings API (gemini-embedding-001, 768-d)
  - huggingface  -> HF Inference API (BAAI/bge-base-en-v1.5, 768-d)
  - mock         -> deterministic hash-based vectors (offline / no key)

All produce vectors of EMBEDDING_DIM to match the pgvector column. The mock
provider keeps the pipeline exercisable offline and in tests.
"""
from __future__ import annotations

import asyncio
import hashlib
import math

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger
from app.services.embedding.cache import EmbeddingCache

logger = get_logger(__name__)

# HF Inference Providers router (the classic api-inference host is deprecated).
_HF_API_URL = (
    "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
)


class EmbeddingService:
    """Generates embeddings for single texts or batches, with an LRU cache."""

    def __init__(self) -> None:
        self._dim = settings.embedding_dim
        self._cache = EmbeddingCache()
        self._provider = self._resolve_provider()
        logger.info("EmbeddingService provider: %s (%d dims)", self._provider, self._dim)

    @staticmethod
    def _resolve_provider() -> str:
        """Pick the active provider, falling back to mock when creds are missing."""
        requested = settings.embedding_provider.lower()
        if requested == "gemini":
            if settings.has_gemini:
                return "gemini"
            logger.warning("EMBEDDING_PROVIDER=gemini but no GEMINI_API_KEY; using mock")
            return "mock"
        if requested == "huggingface":
            if settings.has_hf:
                return "huggingface"
            logger.warning("EMBEDDING_PROVIDER=huggingface but no HF_API_TOKEN; using mock")
            return "mock"
        if requested != "mock":
            logger.warning("Unknown EMBEDDING_PROVIDER '%s'; using mock", requested)
        return "mock"

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
            if self._provider == "huggingface":
                return await self._embed_huggingface(texts)
            return [self._mock_embedding(t) for t in texts]
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(f"Embedding failed: {exc}") from exc

    async def _embed_gemini(self, texts: list[str]) -> list[list[float]]:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        batch_size = max(1, settings.embedding_batch_size)

        def _run() -> list[list[float]]:
            out: list[list[float]] = []
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                resp = genai.embed_content(
                    model=settings.gemini_embedding_model,
                    content=batch,  # batch request -> one round-trip per chunk-group
                    task_type="retrieval_document",
                    # gemini-embedding-001 defaults to 3072 dims; pin to the
                    # pgvector column size so vectors fit the schema.
                    output_dimensionality=self._dim,
                )
                emb = resp["embedding"]
                # A list input returns a list of vectors; a 1-item batch may come
                # back as a single flat vector — normalise both to list-of-vectors.
                if emb and isinstance(emb[0], (int, float)):
                    emb = [emb]
                out.extend(emb)
            return out

        return await asyncio.to_thread(_run)

    async def _embed_huggingface(self, texts: list[str]) -> list[list[float]]:
        url = _HF_API_URL.format(model=settings.hf_embedding_model)
        headers = {"Authorization": f"Bearer {settings.hf_api_token}"}
        batch_size = max(1, settings.embedding_batch_size)
        out: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                resp = await client.post(url, headers=headers, json={"inputs": batch})
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, list):
                    raise EmbeddingError(f"Unexpected HF response: {str(data)[:200]}")
                out.extend(self._normalize_hf(item) for item in data)
        return out

    @staticmethod
    def _normalize_hf(item: list) -> list[float]:
        """Reduce an HF feature-extraction result to a single sentence vector.

        Sentence-transformers models return a pooled 1-D vector; plain encoders
        return token-level 2-D embeddings, which we mean-pool over tokens.
        """
        if not item:
            return []
        if isinstance(item[0], (int, float)):
            return [float(x) for x in item]
        # Token-level [tokens][dim] -> mean-pool across tokens.
        cols = len(item[0])
        sums = [0.0] * cols
        for row in item:
            for j, value in enumerate(row):
                sums[j] += float(value)
        n = len(item)
        return [s / n for s in sums]

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

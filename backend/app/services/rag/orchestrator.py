"""The RAG brain: embed question -> vector search -> build context -> Gemini."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import QueryResponse, Source
from app.services.embedding.service import EmbeddingService
from app.services.llm.gemini_client import GeminiClient
from app.services.rag.prompts import RAG_SYSTEM, build_rag_prompt
from app.services.vector_store.service import VectorMatch, VectorStore

logger = get_logger(__name__)


class RAGOrchestrator:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        gemini: GeminiClient,
    ) -> None:
        self._embedder = embedding_service
        self._store = vector_store
        self._gemini = gemini

    async def answer(
        self, session: AsyncSession, question: str, *, top_k: int | None = None
    ) -> QueryResponse:
        top_k = top_k or settings.retrieval_top_k

        query_vec = await self._embedder.generate_embedding(question)
        matches = await self._store.search(
            session, query_embedding=query_vec, top_k=top_k
        )

        if not matches:
            return QueryResponse(
                answer=(
                    "I couldn't find anything in the knowledge base related to that "
                    "question. Try rephrasing or ensure the relevant documents have "
                    "been uploaded."
                ),
                sources=[],
                confidence_score=0.0,
                related_documents=[],
            )

        context_blocks = self._build_context(matches)
        prompt = build_rag_prompt(question, context_blocks)
        answer_text = await self._gemini.generate(prompt, system=RAG_SYSTEM)

        sources = [
            Source(
                document_id=m.document_id,
                file_name=m.file_name,
                chunk_index=m.chunk_index,
                score=m.score,
            )
            for m in matches
        ]
        related = list(dict.fromkeys(m.file_name for m in matches if m.file_name))
        confidence = self._confidence(matches)

        return QueryResponse(
            answer=answer_text,
            sources=sources,
            confidence_score=confidence,
            related_documents=related,
        )

    @staticmethod
    def _build_context(matches: list[VectorMatch]) -> list[str]:
        blocks: list[str] = []
        for i, m in enumerate(matches, start=1):
            label = m.file_name or m.document_id or f"chunk {i}"
            blocks.append(f"[{i}] (source: {label})\n{m.text}")
        return blocks

    @staticmethod
    def _confidence(matches: list[VectorMatch]) -> float:
        """Average similarity of the top matches, as a rough confidence proxy."""
        top = matches[: min(3, len(matches))]
        if not top:
            return 0.0
        return round(sum(m.score for m in top) / len(top), 3)

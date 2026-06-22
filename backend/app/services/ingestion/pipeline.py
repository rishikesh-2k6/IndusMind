"""Document ingestion pipeline.

Runs after upload: extract -> chunk -> embed -> persist chunks (with embeddings)
into Postgres/pgvector, updating the document status throughout. Owns its own DB
session because it may run outside the request that triggered it.

On Vercel this runs synchronously inside the upload request (serverless has no
durable background workers); on a long-running server it can be awaited or
scheduled — either way the logic is identical.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.repositories.document_repo import DocumentRepository
from app.services.chunking.service import ChunkingService
from app.services.document_processing.service import DocumentProcessor
from app.services.embedding.service import EmbeddingService

logger = get_logger(__name__)


class IngestionPipeline:
    def __init__(
        self,
        *,
        sessionmaker: async_sessionmaker | None,
        processor: DocumentProcessor,
        chunker: ChunkingService,
        embedder: EmbeddingService,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._processor = processor
        self._chunker = chunker
        self._embedder = embedder

    async def run(
        self, *, document_id: uuid.UUID, file_name: str, data: bytes
    ) -> None:
        """Process and index a single document. Marks status failed on error."""
        logger.info("Ingestion started for %s (%s)", document_id, file_name)
        try:
            processed = await self._processor.process(file_name=file_name, data=data)
            chunks = self._chunker.split(processed.text)

            if not chunks:
                await self._finish(document_id, "failed", error="No text extracted")
                return

            embeddings = await self._embedder.generate_batch_embeddings(chunks)
            await self._persist(document_id, chunks, embeddings)
            await self._finish(document_id, "ready", page_count=processed.page_count)
            logger.info("Ingestion complete for %s (%d chunks)", document_id, len(chunks))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ingestion failed for %s", document_id)
            await self._finish(document_id, "failed", error=str(exc)[:500])

    async def _persist(
        self,
        document_id: uuid.UUID,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        async with self._sessionmaker() as session:
            repo = DocumentRepository(session)
            await repo.add_chunks(document_id, chunks, embeddings)
            await session.commit()

    async def _finish(
        self,
        document_id: uuid.UUID,
        status: str,
        *,
        error: str | None = None,
        page_count: int | None = None,
    ) -> None:
        async with self._sessionmaker() as session:
            repo = DocumentRepository(session)
            await repo.set_status(
                document_id, status, error=error, page_count=page_count
            )
            await session.commit()

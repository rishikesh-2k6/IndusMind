"""Service container: builds and holds shared service singletons.

Constructed once at application startup (lifespan) and attached to app.state so
routers and background tasks share the same instances (model clients, caches).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import get_sessionmaker
from app.db.supabase_client import StorageService
from app.services.chunking.service import ChunkingService
from app.services.document_processing.service import DocumentProcessor
from app.services.embedding.service import EmbeddingService
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.llm.gemini_client import GeminiClient
from app.services.rag.orchestrator import RAGOrchestrator
from app.services.summarization.service import SummarizationService
from app.services.vector_store.service import VectorStore


@dataclass
class ServiceContainer:
    sessionmaker: async_sessionmaker | None
    storage: StorageService
    gemini: GeminiClient
    embedder: EmbeddingService
    vector_store: VectorStore
    processor: DocumentProcessor
    chunker: ChunkingService
    rag: RAGOrchestrator
    summarizer: SummarizationService
    ingestion: IngestionPipeline


def build_container() -> ServiceContainer:
    # DB is optional so the API still boots (e.g. /health) without a database.
    sessionmaker = get_sessionmaker() if settings.has_database else None
    storage = StorageService()
    gemini = GeminiClient()
    embedder = EmbeddingService()
    vector_store = VectorStore()
    processor = DocumentProcessor()
    chunker = ChunkingService()

    rag = RAGOrchestrator(embedder, vector_store, gemini)
    summarizer = SummarizationService(gemini)
    ingestion = IngestionPipeline(
        sessionmaker=sessionmaker,
        processor=processor,
        chunker=chunker,
        embedder=embedder,
    )

    return ServiceContainer(
        sessionmaker=sessionmaker,
        storage=storage,
        gemini=gemini,
        embedder=embedder,
        vector_store=vector_store,
        processor=processor,
        chunker=chunker,
        rag=rag,
        summarizer=summarizer,
        ingestion=ingestion,
    )

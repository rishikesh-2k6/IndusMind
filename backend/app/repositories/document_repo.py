"""Data access for documents and their chunks."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chunk, Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        file_name: str,
        file_type: str,
        storage_path: str,
        uploaded_by: uuid.UUID | None,
    ) -> Document:
        doc = Document(
            file_name=file_name,
            file_type=file_type,
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            status="processing",
        )
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def get(self, document_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[Document]:
        stmt = (
            select(Document)
            .order_by(Document.upload_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def set_status(
        self,
        document_id: uuid.UUID,
        status: str,
        *,
        error: str | None = None,
        page_count: int | None = None,
    ) -> None:
        doc = await self._session.get(Document, document_id)
        if doc is None:
            return
        doc.status = status
        doc.error = error
        if page_count is not None:
            doc.page_count = page_count

    async def add_chunks(
        self,
        document_id: uuid.UUID,
        chunks: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> list[Chunk]:
        objs = [
            Chunk(
                document_id=document_id,
                chunk_index=i,
                text=text,
                embedding=embeddings[i] if embeddings is not None else None,
            )
            for i, text in enumerate(chunks)
        ]
        self._session.add_all(objs)
        await self._session.flush()
        return objs

    async def get_chunks(self, document_id: uuid.UUID) -> list[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, document_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(Document).where(Document.id == document_id)
        )

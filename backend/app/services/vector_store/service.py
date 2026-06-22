"""Supabase pgvector similarity search over the chunks table.

Vectors live alongside their text in the `chunks` table, so deleting a document
(chunks cascade) also removes its vectors — there is no separate vector store to
keep in sync. Indexing happens when chunks are inserted with their embeddings.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chunk, Document


@dataclass(slots=True)
class VectorMatch:
    chunk_id: str
    document_id: str
    file_name: str
    chunk_index: int
    text: str
    score: float  # cosine similarity in [0, 1] (higher = closer)


class VectorStore:
    """Cosine-similarity search backed by pgvector."""

    async def search(
        self,
        session: AsyncSession,
        *,
        query_embedding: list[float],
        top_k: int,
        document_id: uuid.UUID | None = None,
    ) -> list[VectorMatch]:
        distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.chunk_index,
                Chunk.text,
                Document.file_name,
                distance,
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.embedding.isnot(None))
            .order_by(distance)
            .limit(top_k)
        )
        if document_id is not None:
            stmt = stmt.where(Chunk.document_id == document_id)

        rows = (await session.execute(stmt)).all()
        matches: list[VectorMatch] = []
        for cid, doc_id, idx, text, file_name, dist in rows:
            # cosine_distance is in [0, 2]; similarity = 1 - distance.
            score = max(0.0, 1.0 - float(dist))
            matches.append(
                VectorMatch(
                    chunk_id=str(cid),
                    document_id=str(doc_id),
                    file_name=file_name or "",
                    chunk_index=int(idx),
                    text=text or "",
                    score=round(score, 4),
                )
            )
        return matches

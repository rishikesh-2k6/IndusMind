"""User-facing AI Copilot: query (RAG), raw search, and summarization."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer
from app.core.deps import get_container, get_db, require_user
from app.core.exceptions import NotFoundError
from app.models.schemas import (
    CurrentUser,
    DocumentOut,
    QueryRequest,
    QueryResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SummarizeRequest,
    SummarizeResponse,
)
from app.repositories.chat_repo import ChatRepository
from app.repositories.document_repo import DocumentRepository

router = APIRouter(tags=["copilot"])


@router.get("/library", response_model=list[DocumentOut])
async def library(
    _: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentOut]:
    """Read-only document list for the copilot sidebar (any authenticated user)."""
    docs = await DocumentRepository(db).list_all(limit=200)
    return [DocumentOut.model_validate(d) for d in docs]


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    user: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    container: Annotated[ServiceContainer, Depends(get_container)],
) -> QueryResponse:
    chat_repo = ChatRepository(db)

    # Resolve or create the chat session.
    session_id = body.session_id
    if session_id is not None:
        existing = await chat_repo.get_session(session_id, user_id=user.id)
        if existing is None:
            raise NotFoundError("Chat session not found")
    else:
        new_session = await chat_repo.create_session(
            user_id=user.id, title=body.question[:80]
        )
        session_id = new_session.id

    await chat_repo.add_message(session_id=session_id, role="user", content=body.question)

    response = await container.rag.answer(db, body.question, top_k=body.top_k)

    await chat_repo.add_message(
        session_id=session_id,
        role="assistant",
        content=response.answer,
        sources=[s.model_dump() for s in response.sources],
    )

    response.session_id = session_id
    return response


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    _: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    container: Annotated[ServiceContainer, Depends(get_container)],
) -> SearchResponse:
    query_vec = await container.embedder.generate_embedding(body.query)
    matches = await container.vector_store.search(
        db,
        query_embedding=query_vec,
        top_k=body.top_k,
        document_id=body.document_id,
    )
    results = [
        SearchResult(
            chunk_id=m.chunk_id,
            document_id=m.document_id,
            file_name=m.file_name,
            chunk_index=m.chunk_index,
            text=m.text,
            score=m.score,
        )
        for m in matches
    ]
    return SearchResponse(results=results)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    body: SummarizeRequest,
    _: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    container: Annotated[ServiceContainer, Depends(get_container)],
) -> SummarizeResponse:
    return await container.summarizer.summarize(
        db, document_ids=body.document_ids, focus=body.focus
    )

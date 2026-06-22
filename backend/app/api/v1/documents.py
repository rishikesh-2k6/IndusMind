"""Admin document management: upload, list, detail, status, delete."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer
from app.core.deps import get_container, get_db, require_admin
from app.core.exceptions import NotFoundError
from app.models.schemas import (
    CurrentUser,
    DocumentOut,
    DocumentStatusOut,
    UploadResponse,
)
from app.repositories.document_repo import DocumentRepository
from app.services.document_processing.extractor import detect_file_type

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    container: Annotated[ServiceContainer, Depends(get_container)],
    file: UploadFile = File(...),
) -> UploadResponse:
    file_name = file.filename or "upload"
    # Validate type up-front so unsupported files fail fast (raises 415).
    file_type = detect_file_type(file_name)
    data = await file.read()

    repo = DocumentRepository(db)
    doc = await repo.create(
        file_name=file_name,
        file_type=file_type,
        storage_path="",  # set after we know the document id
        uploaded_by=admin.id,
    )

    storage_path = f"{doc.id}/{file_name}"
    await container.storage.upload(
        storage_path, data, file.content_type or "application/octet-stream"
    )
    doc.storage_path = storage_path
    doc_id = doc.id
    # Commit the document row before ingestion so it exists in its own session.
    await db.commit()

    # Process and index synchronously (serverless has no durable background tasks).
    await container.ingestion.run(document_id=doc_id, file_name=file_name, data=data)

    refreshed = await repo.get(doc_id)
    final_status = refreshed.status if refreshed else "processing"
    return UploadResponse(document_id=doc_id, file_name=file_name, status=final_status)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    _: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[DocumentOut]:
    docs = await DocumentRepository(db).list_all(limit=limit, offset=offset)
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    _: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentOut:
    doc = await DocumentRepository(db).get(document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    return DocumentOut.model_validate(doc)


@router.get("/{document_id}/status", response_model=DocumentStatusOut)
async def get_document_status(
    document_id: uuid.UUID,
    _: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentStatusOut:
    doc = await DocumentRepository(db).get(document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    return DocumentStatusOut.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    _: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    container: Annotated[ServiceContainer, Depends(get_container)],
) -> None:
    repo = DocumentRepository(db)
    doc = await repo.get(document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")

    # Remove the stored file, then the DB rows. Chunks (and their pgvector
    # embeddings) cascade-delete with the document.
    if doc.storage_path:
        await container.storage.delete(doc.storage_path)
    await repo.delete(document_id)

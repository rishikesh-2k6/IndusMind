"""Pydantic request/response schemas (the JSON contracts for the frontend)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


class CurrentUser(BaseModel):
    id: uuid.UUID
    email: str | None = None
    role: Literal["admin", "user"] = "user"


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


class DocumentOut(BaseModel):
    id: uuid.UUID
    file_name: str
    file_type: str
    page_count: int
    status: str
    error: str | None = None
    upload_date: datetime

    model_config = {"from_attributes": True}


class DocumentStatusOut(BaseModel):
    id: uuid.UUID
    status: str
    error: str | None = None

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    document_id: uuid.UUID
    file_name: str
    status: str = "processing"


# --------------------------------------------------------------------------- #
# Query / RAG
# --------------------------------------------------------------------------- #


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    session_id: uuid.UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)


class Source(BaseModel):
    document_id: str
    file_name: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    confidence_score: float = 0.0
    related_documents: list[str] = Field(default_factory=list)
    session_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Search (raw retrieval)
# --------------------------------------------------------------------------- #


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    document_id: uuid.UUID | None = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    chunk_index: int
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Summarization
# --------------------------------------------------------------------------- #


class SummarizeRequest(BaseModel):
    document_ids: list[uuid.UUID] = Field(..., min_length=1)
    focus: str | None = Field(default=None, max_length=500)


class SummarizeResponse(BaseModel):
    summary: str
    document_ids: list[uuid.UUID]
    related_documents: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Chat history
# --------------------------------------------------------------------------- #


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: list | dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    title: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetail(ChatSessionOut):
    messages: list[ChatMessageOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Knowledge graph
# --------------------------------------------------------------------------- #


class EquipmentOut(BaseModel):
    key: str
    label: str
    mentions: int


class EquipmentEventOut(BaseModel):
    relation: str
    kind: str
    key: str
    label: str
    date: str | None = None
    summary: str | None = None
    document_id: str | None = None


class EquipmentHistoryOut(BaseModel):
    key: str
    events: list[EquipmentEventOut] = Field(default_factory=list)


class FailurePatternOut(BaseModel):
    failure_key: str
    failure_label: str
    occurrences: int
    equipment_count: int
    equipment: list[str] = Field(default_factory=list)


class KgStatsOut(BaseModel):
    entities: int
    relations: int
    equipment: int

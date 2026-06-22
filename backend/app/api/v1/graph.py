"""Knowledge-graph endpoints: equipment history & failure patterns."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_user
from app.models.schemas import (
    CurrentUser,
    EquipmentHistoryOut,
    EquipmentOut,
    FailurePatternOut,
    KgStatsOut,
)
from app.repositories.kg_repo import KnowledgeGraphRepository
from app.services.entity_extraction.service import normalize_key

router = APIRouter(tags=["knowledge-graph"])


@router.get("/equipment", response_model=list[EquipmentOut])
async def list_equipment(
    _: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EquipmentOut]:
    rows = await KnowledgeGraphRepository(db).list_equipment()
    return [EquipmentOut(**r) for r in rows]


@router.get("/equipment/{key}/history", response_model=EquipmentHistoryOut)
async def equipment_history(
    key: str,
    _: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EquipmentHistoryOut:
    norm = normalize_key(key)
    events = await KnowledgeGraphRepository(db).equipment_history(norm)
    return EquipmentHistoryOut(key=norm, events=events)


@router.get("/failure-patterns", response_model=list[FailurePatternOut])
async def failure_patterns(
    _: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    min_count: int = 1,
) -> list[FailurePatternOut]:
    rows = await KnowledgeGraphRepository(db).failure_patterns(min_count=min_count)
    return [FailurePatternOut(**r) for r in rows]


@router.get("/graph/stats", response_model=KgStatsOut)
async def graph_stats(
    _: Annotated[CurrentUser, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KgStatsOut:
    return KgStatsOut(**await KnowledgeGraphRepository(db).stats())

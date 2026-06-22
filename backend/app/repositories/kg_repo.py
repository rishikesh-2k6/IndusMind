"""Data access for the knowledge graph (entities + relations)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import KgEntity, KgRelation


class KnowledgeGraphRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_entities(self, document_id: uuid.UUID, entities: list[dict]) -> int:
        objs = [
            KgEntity(
                document_id=document_id,
                kind=e["kind"],
                key=e["key"],
                label=e["label"],
                attributes=e.get("attributes"),
            )
            for e in entities
        ]
        self._session.add_all(objs)
        await self._session.flush()
        return len(objs)

    async def add_relations(self, document_id: uuid.UUID, relations: list[dict]) -> int:
        objs = [
            KgRelation(
                document_id=document_id,
                src_kind=r["src_kind"], src_key=r["src_key"],
                dst_kind=r["dst_kind"], dst_key=r["dst_key"],
                relation=r["relation"],
                attributes=r.get("attributes"),
            )
            for r in relations
        ]
        self._session.add_all(objs)
        await self._session.flush()
        return len(objs)

    async def list_equipment(self) -> list[dict]:
        """Distinct equipment with a representative label and mention count."""
        stmt = (
            select(
                KgEntity.key,
                func.max(KgEntity.label).label("label"),
                func.count(KgEntity.id).label("mentions"),
            )
            .where(KgEntity.kind == "equipment")
            .group_by(KgEntity.key)
            .order_by(func.count(KgEntity.id).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [{"key": k, "label": lbl, "mentions": m} for k, lbl, m in rows]

    async def equipment_history(self, key: str) -> list[dict]:
        """All relations where this equipment is the source, newest-looking first."""
        rel = KgRelation
        ent = KgEntity
        stmt = (
            select(
                rel.relation,
                rel.dst_kind,
                rel.dst_key,
                rel.attributes,
                rel.document_id,
                func.max(ent.label).label("dst_label"),
            )
            .outerjoin(ent, (ent.kind == rel.dst_kind) & (ent.key == rel.dst_key))
            .where(rel.src_kind == "equipment", rel.src_key == key)
            .group_by(rel.relation, rel.dst_kind, rel.dst_key, rel.attributes, rel.document_id)
        )
        rows = (await self._session.execute(stmt)).all()
        events = []
        for relation, dst_kind, dst_key, attrs, doc_id, dst_label in rows:
            attrs = attrs or {}
            events.append({
                "relation": relation,
                "kind": dst_kind,
                "key": dst_key,
                "label": dst_label or dst_key,
                "date": attrs.get("date"),
                "summary": attrs.get("summary") or attrs.get("result"),
                "attributes": attrs,
                "document_id": str(doc_id) if doc_id else None,
            })
        # Sort by date when present (string ISO sorts chronologically), newest first.
        events.sort(key=lambda e: e.get("date") or "", reverse=True)
        return events

    async def failure_patterns(self, *, min_count: int = 1) -> list[dict]:
        """Failures grouped by type, with occurrence count and affected equipment."""
        rel = KgRelation
        stmt = (
            select(
                rel.dst_key,
                func.count(rel.id).label("occurrences"),
                func.count(func.distinct(rel.src_key)).label("equipment_count"),
            )
            .where(rel.relation == "has_failure", rel.dst_kind == "failure")
            .group_by(rel.dst_key)
            .having(func.count(rel.id) >= min_count)
            .order_by(func.count(rel.id).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        patterns = []
        for dst_key, occurrences, equip_count in rows:
            # Pull a label and the affected equipment keys.
            label_stmt = select(func.max(KgEntity.label)).where(
                KgEntity.kind == "failure", KgEntity.key == dst_key
            )
            label = (await self._session.execute(label_stmt)).scalar() or dst_key
            equip_stmt = (
                select(func.distinct(rel.src_key))
                .where(rel.relation == "has_failure", rel.dst_key == dst_key)
            )
            equipment = [r[0] for r in (await self._session.execute(equip_stmt)).all()]
            patterns.append({
                "failure_key": dst_key,
                "failure_label": label,
                "occurrences": occurrences,
                "equipment_count": equip_count,
                "equipment": equipment,
            })
        return patterns

    async def stats(self) -> dict:
        n_ent = (await self._session.execute(select(func.count(KgEntity.id)))).scalar()
        n_rel = (await self._session.execute(select(func.count(KgRelation.id)))).scalar()
        n_equip = (await self._session.execute(
            select(func.count(func.distinct(KgEntity.key))).where(KgEntity.kind == "equipment")
        )).scalar()
        return {"entities": n_ent or 0, "relations": n_rel or 0, "equipment": n_equip or 0}

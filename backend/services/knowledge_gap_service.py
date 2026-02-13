"""
Knowledge Gap service for detecting and managing knowledge gaps.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, update, case
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import KnowledgeGap, GapStatus


class KnowledgeGapService:
    """Service for knowledge gap operations with optimized queries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_gap(
        self,
        tenant_id: UUID,
        question: str,
        category: Optional[str] = None,
        priority: int = 1,
        source_document_ids: Optional[List[str]] = None
    ) -> KnowledgeGap:
        """Create a new knowledge gap."""
        gap = KnowledgeGap(
            tenant_id=tenant_id,
            question=question,
            category=category,
            priority=priority,
            source_document_ids=source_document_ids or []
        )
        self.db.add(gap)
        await self.db.flush()
        return gap

    async def create_gaps_bulk(
        self,
        tenant_id: UUID,
        gaps_data: List[Dict[str, Any]]
    ) -> List[KnowledgeGap]:
        """Create multiple gaps in a single operation."""
        gaps = []
        for data in gaps_data:
            gap = KnowledgeGap(
                tenant_id=tenant_id,
                question=data["question"],
                category=data.get("category"),
                priority=data.get("priority", 1),
                source_document_ids=data.get("source_document_ids", [])
            )
            gaps.append(gap)

        self.db.add_all(gaps)
        await self.db.flush()
        return gaps

    async def get_gap(self, gap_id: UUID, tenant_id: UUID) -> Optional[KnowledgeGap]:
        """Get a single gap by ID."""
        result = await self.db.execute(
            select(KnowledgeGap).where(
                and_(
                    KnowledgeGap.id == gap_id,
                    KnowledgeGap.tenant_id == tenant_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_gaps(
        self,
        tenant_id: UUID,
        status: Optional[GapStatus] = None,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[KnowledgeGap], int]:
        """Get gaps with filtering and pagination."""
        query = select(KnowledgeGap).where(KnowledgeGap.tenant_id == tenant_id)
        count_query = select(func.count(KnowledgeGap.id)).where(KnowledgeGap.tenant_id == tenant_id)

        if status:
            query = query.where(KnowledgeGap.status == status)
            count_query = count_query.where(KnowledgeGap.status == status)
        if category:
            query = query.where(KnowledgeGap.category == category)
            count_query = count_query.where(KnowledgeGap.category == category)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Get gaps with sorting and pagination
        query = query.order_by(
            KnowledgeGap.priority.desc(),
            KnowledgeGap.created_at.desc()
        ).limit(limit).offset(offset)

        result = await self.db.execute(query)
        gaps = result.scalars().all()

        return list(gaps), total

    async def answer_gap(
        self,
        gap_id: UUID,
        tenant_id: UUID,
        answer: str
    ) -> Optional[KnowledgeGap]:
        """Answer a knowledge gap."""
        gap = await self.get_gap(gap_id, tenant_id)
        if not gap:
            return None

        gap.answer = answer
        gap.status = GapStatus.ANSWERED
        gap.answered_at = datetime.utcnow()
        gap.updated_at = datetime.utcnow()

        await self.db.flush()
        return gap

    async def dismiss_gap(self, gap_id: UUID, tenant_id: UUID) -> bool:
        """Dismiss a knowledge gap."""
        result = await self.db.execute(
            update(KnowledgeGap)
            .where(
                and_(
                    KnowledgeGap.id == gap_id,
                    KnowledgeGap.tenant_id == tenant_id
                )
            )
            .values(status=GapStatus.DISMISSED, updated_at=datetime.utcnow())
        )
        return result.rowcount > 0

    async def bulk_dismiss(self, gap_ids: List[UUID], tenant_id: UUID) -> int:
        """Dismiss multiple gaps in one query."""
        if not gap_ids:
            return 0

        result = await self.db.execute(
            update(KnowledgeGap)
            .where(
                and_(
                    KnowledgeGap.id.in_(gap_ids),
                    KnowledgeGap.tenant_id == tenant_id
                )
            )
            .values(status=GapStatus.DISMISSED, updated_at=datetime.utcnow())
        )
        return result.rowcount

    async def get_gap_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        Get gap statistics in a single aggregated query.
        Fixes the multiple COUNT queries issue.
        """
        result = await self.db.execute(
            select(
                func.count(KnowledgeGap.id).label("total"),
                func.sum(case((KnowledgeGap.status == GapStatus.OPEN, 1), else_=0)).label("open"),
                func.sum(case((KnowledgeGap.status == GapStatus.ANSWERED, 1), else_=0)).label("answered"),
                func.sum(case((KnowledgeGap.status == GapStatus.DISMISSED, 1), else_=0)).label("dismissed"),
                func.sum(case((KnowledgeGap.priority >= 4, 1), else_=0)).label("high_priority"),
            ).where(KnowledgeGap.tenant_id == tenant_id)
        )
        row = result.fetchone()

        return {
            "total": row.total or 0,
            "open": row.open or 0,
            "answered": row.answered or 0,
            "dismissed": row.dismissed or 0,
            "high_priority": row.high_priority or 0,
        }

    async def get_categories(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """Get all categories with counts."""
        result = await self.db.execute(
            select(
                KnowledgeGap.category,
                func.count(KnowledgeGap.id).label("count")
            )
            .where(
                and_(
                    KnowledgeGap.tenant_id == tenant_id,
                    KnowledgeGap.category.isnot(None)
                )
            )
            .group_by(KnowledgeGap.category)
            .order_by(func.count(KnowledgeGap.id).desc())
        )

        return [
            {"category": row.category, "count": row.count}
            for row in result.fetchall()
        ]

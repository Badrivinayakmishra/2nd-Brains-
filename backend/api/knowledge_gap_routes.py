"""
Knowledge Gap API routes.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, Tenant, GapStatus
from services.knowledge_gap_service import KnowledgeGapService
from api.auth_routes import get_current_tenant

router = APIRouter(prefix="/knowledge-gaps", tags=["Knowledge Gaps"])


# ============== Schemas ==============

class GapCreate(BaseModel):
    question: str
    category: Optional[str] = None
    priority: int = 1


class GapResponse(BaseModel):
    id: UUID
    question: str
    category: Optional[str]
    priority: int
    status: GapStatus
    answer: Optional[str]
    answered_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class GapListResponse(BaseModel):
    gaps: List[GapResponse]
    total: int
    page: int
    per_page: int


class AnswerGapRequest(BaseModel):
    answer: str


class GapStatsResponse(BaseModel):
    total: int
    open: int
    answered: int
    dismissed: int
    high_priority: int


class CategoryResponse(BaseModel):
    category: str
    count: int


# ============== Routes ==============

@router.get("", response_model=GapListResponse)
async def list_gaps(
    status: Optional[GapStatus] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """List knowledge gaps with filtering."""
    service = KnowledgeGapService(db)
    offset = (page - 1) * per_page

    gaps, total = await service.get_gaps(
        tenant_id=tenant.id,
        status=status,
        category=category,
        limit=per_page,
        offset=offset
    )

    return GapListResponse(
        gaps=[GapResponse.model_validate(g) for g in gaps],
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/stats", response_model=GapStatsResponse)
async def get_gap_stats(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Get knowledge gap statistics."""
    service = KnowledgeGapService(db)
    stats = await service.get_gap_stats(tenant.id)
    return GapStatsResponse(**stats)


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Get all categories with counts."""
    service = KnowledgeGapService(db)
    categories = await service.get_categories(tenant.id)
    return [CategoryResponse(**c) for c in categories]


@router.post("", response_model=GapResponse, status_code=status.HTTP_201_CREATED)
async def create_gap(
    data: GapCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new knowledge gap manually."""
    service = KnowledgeGapService(db)
    gap = await service.create_gap(
        tenant_id=tenant.id,
        question=data.question,
        category=data.category,
        priority=data.priority
    )
    return GapResponse.model_validate(gap)


@router.get("/{gap_id}", response_model=GapResponse)
async def get_gap(
    gap_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Get a single knowledge gap."""
    service = KnowledgeGapService(db)
    gap = await service.get_gap(gap_id, tenant.id)

    if not gap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gap not found"
        )

    return GapResponse.model_validate(gap)


@router.post("/{gap_id}/answer", response_model=GapResponse)
async def answer_gap(
    gap_id: UUID,
    request: AnswerGapRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Answer a knowledge gap."""
    service = KnowledgeGapService(db)
    gap = await service.answer_gap(gap_id, tenant.id, request.answer)

    if not gap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gap not found"
        )

    return GapResponse.model_validate(gap)


@router.post("/{gap_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_gap(
    gap_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Dismiss a knowledge gap."""
    service = KnowledgeGapService(db)
    dismissed = await service.dismiss_gap(gap_id, tenant.id)

    if not dismissed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gap not found"
        )


@router.post("/bulk/dismiss")
async def bulk_dismiss_gaps(
    gap_ids: List[UUID],
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Dismiss multiple gaps at once."""
    service = KnowledgeGapService(db)
    count = await service.bulk_dismiss(gap_ids, tenant.id)
    return {"dismissed": count}

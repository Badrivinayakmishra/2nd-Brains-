"""
Document API routes with optimized batch operations.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, Document, DocumentStatus, Tenant
from services.document_service import DocumentService
from api.auth_routes import get_current_tenant

router = APIRouter(prefix="/documents", tags=["Documents"])


# ============== Schemas ==============

class DocumentCreate(BaseModel):
    title: str
    content: Optional[str] = None
    source_url: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Optional[dict] = None


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    content: Optional[str]
    status: DocumentStatus
    classification: Optional[str]
    classification_confidence: Optional[float]
    project_id: Optional[UUID]
    source_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    per_page: int


class BulkClassifyRequest(BaseModel):
    document_ids: List[UUID]
    classification: str


class BulkDeleteRequest(BaseModel):
    document_ids: List[UUID]


class DocumentStatsResponse(BaseModel):
    total: int
    pending: int
    processing: int
    classified: int
    indexed: int
    failed: int
    in_vector_db: int


# ============== Routes ==============

@router.get("", response_model=DocumentListResponse)
async def list_documents(
    status: Optional[DocumentStatus] = None,
    project_id: Optional[UUID] = None,
    connector_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    List documents with filtering and pagination.
    Uses optimized query with single count.
    """
    service = DocumentService(db)
    offset = (page - 1) * per_page

    documents, total = await service.get_documents(
        tenant_id=tenant.id,
        status=status,
        project_id=project_id,
        connector_id=connector_id,
        limit=per_page,
        offset=offset
    )

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/stats", response_model=DocumentStatsResponse)
async def get_document_stats(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Get document statistics.
    Uses single aggregated query instead of multiple COUNTs.
    """
    service = DocumentService(db)
    stats = await service.get_document_stats(tenant.id)
    return DocumentStatsResponse(**stats)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc_data: DocumentCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new document."""
    service = DocumentService(db)
    document = await service.create_document(
        tenant_id=tenant.id,
        title=doc_data.title,
        content=doc_data.content,
        source_url=doc_data.source_url,
        mime_type=doc_data.mime_type,
        metadata=doc_data.metadata
    )
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Get a single document."""
    service = DocumentService(db)
    document = await service.get_document(document_id, tenant.id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Delete a single document."""
    service = DocumentService(db)
    deleted = await service.bulk_delete_documents([document_id], tenant.id)

    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )


@router.post("/bulk/classify")
async def bulk_classify_documents(
    request: BulkClassifyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Classify multiple documents at once.
    Fixes N+1 issue: 100 docs = 1 query instead of 100.
    """
    service = DocumentService(db)

    # Verify all documents belong to tenant
    docs = await service.get_documents_by_ids(request.document_ids, tenant.id)
    if len(docs) != len(request.document_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some documents not found or don't belong to you"
        )

    count = await service.bulk_classify_documents(
        document_ids=request.document_ids,
        classification=request.classification
    )

    return {"classified": count}


@router.post("/bulk/delete")
async def bulk_delete_documents(
    request: BulkDeleteRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete multiple documents at once.
    Uses batching to prevent table locks.
    """
    service = DocumentService(db)
    count = await service.bulk_delete_documents(
        document_ids=request.document_ids,
        tenant_id=tenant.id,
        batch_size=100
    )

    return {"deleted": count}


@router.post("/bulk/assign-project")
async def bulk_assign_project(
    document_ids: List[UUID],
    project_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Assign multiple documents to a project."""
    service = DocumentService(db)
    count = await service.bulk_assign_project(document_ids, project_id)

    return {"assigned": count}

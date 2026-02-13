"""
Integration/Connector API routes with proper sync progress tracking.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, Tenant, Connector, ConnectorType, SyncProgress
from api.auth_routes import get_current_tenant

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ============== Schemas ==============

class ConnectorCreate(BaseModel):
    connector_type: ConnectorType
    name: str
    credentials: Optional[dict] = None


class ConnectorResponse(BaseModel):
    id: UUID
    connector_type: ConnectorType
    name: str
    is_active: bool
    last_sync_at: Optional[datetime]
    sync_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SyncProgressResponse(BaseModel):
    status: str
    total_items: int
    processed_items: int
    indexed_items: int
    failed_items: int
    current_step: Optional[str]
    error_message: Optional[str]
    percent: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


# ============== Routes ==============

@router.get("/connectors", response_model=List[ConnectorResponse])
async def list_connectors(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """List all connectors for tenant."""
    result = await db.execute(
        select(Connector).where(Connector.tenant_id == tenant.id)
    )
    connectors = result.scalars().all()
    return [ConnectorResponse.model_validate(c) for c in connectors]


@router.post("/connectors", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    data: ConnectorCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new connector."""
    connector = Connector(
        tenant_id=tenant.id,
        connector_type=data.connector_type,
        name=data.name,
        credentials=data.credentials or {}
    )
    db.add(connector)
    await db.flush()
    return ConnectorResponse.model_validate(connector)


@router.get("/connectors/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Get a connector."""
    result = await db.execute(
        select(Connector).where(
            and_(
                Connector.id == connector_id,
                Connector.tenant_id == tenant.id
            )
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    return ConnectorResponse.model_validate(connector)


@router.delete("/connectors/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Delete a connector."""
    result = await db.execute(
        select(Connector).where(
            and_(
                Connector.id == connector_id,
                Connector.tenant_id == tenant.id
            )
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    await db.delete(connector)


@router.post("/connectors/{connector_id}/sync")
async def start_sync(
    connector_id: UUID,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Start syncing a connector.
    Runs sync in background to avoid blocking.
    """
    result = await db.execute(
        select(Connector).where(
            and_(
                Connector.id == connector_id,
                Connector.tenant_id == tenant.id
            )
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Check if already syncing
    if connector.sync_status == "syncing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync already in progress"
        )

    # Create/reset progress tracking
    progress_result = await db.execute(
        select(SyncProgress).where(SyncProgress.connector_id == connector_id)
    )
    progress = progress_result.scalar_one_or_none()

    if not progress:
        progress = SyncProgress(connector_id=connector_id)
        db.add(progress)

    progress.status = "syncing"
    progress.total_items = 0
    progress.processed_items = 0
    progress.indexed_items = 0
    progress.failed_items = 0
    progress.current_step = "Starting sync..."
    progress.error_message = None
    progress.started_at = datetime.utcnow()
    progress.completed_at = None

    connector.sync_status = "syncing"
    await db.flush()

    # Add background sync task
    background_tasks.add_task(
        run_sync_task,
        connector_id=connector_id,
        connector_type=connector.connector_type,
        credentials=connector.credentials,
        tenant_id=tenant.id
    )

    return {"message": "Sync started", "connector_id": str(connector_id)}


@router.get("/connectors/{connector_id}/progress", response_model=SyncProgressResponse)
async def get_sync_progress(
    connector_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync progress for a connector.
    Used for polling progress on frontend.
    """
    # Verify connector belongs to tenant
    result = await db.execute(
        select(Connector).where(
            and_(
                Connector.id == connector_id,
                Connector.tenant_id == tenant.id
            )
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found"
        )

    # Get progress
    progress_result = await db.execute(
        select(SyncProgress).where(SyncProgress.connector_id == connector_id)
    )
    progress = progress_result.scalar_one_or_none()

    if not progress:
        return SyncProgressResponse(
            status="idle",
            total_items=0,
            processed_items=0,
            indexed_items=0,
            failed_items=0,
            current_step=None,
            error_message=None,
            percent=0,
            started_at=None,
            completed_at=None
        )

    # Calculate percent
    percent = 0
    if progress.total_items > 0:
        percent = (progress.processed_items / progress.total_items) * 100

    return SyncProgressResponse(
        status=progress.status,
        total_items=progress.total_items,
        processed_items=progress.processed_items,
        indexed_items=progress.indexed_items,
        failed_items=progress.failed_items,
        current_step=progress.current_step,
        error_message=progress.error_message,
        percent=round(percent, 1),
        started_at=progress.started_at,
        completed_at=progress.completed_at
    )


# ============== OAuth Routes ==============

@router.get("/{connector_type}/oauth/url")
async def get_oauth_url(
    connector_type: ConnectorType,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Get OAuth authorization URL for a connector."""
    from connectors import get_connector_class

    connector_class = get_connector_class(connector_type)
    if not connector_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector type: {connector_type}"
        )

    url = connector_class.get_oauth_url(str(tenant.id))
    return {"url": url}


@router.post("/{connector_type}/oauth/callback")
async def oauth_callback(
    connector_type: ConnectorType,
    request: OAuthCallbackRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback and create connector."""
    from connectors import get_connector_class

    connector_class = get_connector_class(connector_type)
    if not connector_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector type: {connector_type}"
        )

    try:
        credentials = await connector_class.exchange_code(request.code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code: {str(e)}"
        )

    # Create or update connector
    result = await db.execute(
        select(Connector).where(
            and_(
                Connector.tenant_id == tenant.id,
                Connector.connector_type == connector_type
            )
        )
    )
    connector = result.scalar_one_or_none()

    if connector:
        connector.credentials = credentials
        connector.is_active = True
    else:
        connector = Connector(
            tenant_id=tenant.id,
            connector_type=connector_type,
            name=connector_type.value.replace("_", " ").title(),
            credentials=credentials,
            is_active=True
        )
        db.add(connector)

    await db.flush()
    return ConnectorResponse.model_validate(connector)


# ============== Background Sync Task ==============

async def run_sync_task(
    connector_id: UUID,
    connector_type: ConnectorType,
    credentials: dict,
    tenant_id: UUID
):
    """Background task to run sync."""
    from database.connection import get_db_context
    from connectors import get_connector_class
    from services.document_service import DocumentService
    from services.vector_service import VectorService

    async with get_db_context() as db:
        try:
            # Get progress record
            progress_result = await db.execute(
                select(SyncProgress).where(SyncProgress.connector_id == connector_id)
            )
            progress = progress_result.scalar_one()

            # Get connector class
            connector_class = get_connector_class(connector_type)
            if not connector_class:
                progress.status = "failed"
                progress.error_message = f"Unknown connector type: {connector_type}"
                await db.commit()
                return

            # Initialize connector
            connector_instance = connector_class(credentials)

            # Fetch items
            progress.current_step = "Fetching items from source..."
            await db.commit()

            items = await connector_instance.fetch_items()
            progress.total_items = len(items)
            progress.current_step = f"Processing {len(items)} items..."
            await db.commit()

            # Process items
            doc_service = DocumentService(db)
            vector_service = VectorService()

            # Find existing documents to avoid duplicates
            external_ids = [item.get("external_id") for item in items if item.get("external_id")]
            existing = await doc_service.find_by_external_ids(external_ids, connector_id)

            new_items = []
            for item in items:
                ext_id = item.get("external_id")
                if ext_id and ext_id in existing:
                    # Update existing
                    pass
                else:
                    new_items.append(item)

            # Create new documents in bulk
            if new_items:
                docs = await doc_service.create_documents_bulk(
                    tenant_id=tenant_id,
                    documents=[{
                        "title": item.get("title", "Untitled"),
                        "content": item.get("content", ""),
                        "connector_id": connector_id,
                        "external_id": item.get("external_id"),
                        "source_url": item.get("source_url"),
                        "metadata": item.get("metadata", {})
                    } for item in new_items]
                )
                progress.processed_items = len(docs)

                # Index in vector store
                progress.current_step = "Indexing documents..."
                await db.commit()

                indexed = await vector_service.upsert_documents_batch(
                    documents=[{
                        "id": str(d.id),
                        "title": d.title,
                        "content": d.content or "",
                    } for d in docs],
                    tenant_id=str(tenant_id)
                )
                progress.indexed_items = len(indexed)

            # Mark complete
            progress.status = "completed"
            progress.current_step = "Sync completed"
            progress.completed_at = datetime.utcnow()

            # Update connector
            connector_result = await db.execute(
                select(Connector).where(Connector.id == connector_id)
            )
            connector = connector_result.scalar_one()
            connector.sync_status = "completed"
            connector.last_sync_at = datetime.utcnow()

            await db.commit()

        except Exception as e:
            # Handle error
            progress_result = await db.execute(
                select(SyncProgress).where(SyncProgress.connector_id == connector_id)
            )
            progress = progress_result.scalar_one_or_none()
            if progress:
                progress.status = "failed"
                progress.error_message = str(e)
                progress.completed_at = datetime.utcnow()

            connector_result = await db.execute(
                select(Connector).where(Connector.id == connector_id)
            )
            connector = connector_result.scalar_one_or_none()
            if connector:
                connector.sync_status = "failed"
                connector.sync_error = str(e)

            await db.commit()

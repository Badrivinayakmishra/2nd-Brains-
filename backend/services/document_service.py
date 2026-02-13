"""
Document service with optimized batch operations.
Fixes N+1 query issues from the original codebase.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
import hashlib

from sqlalchemy import select, func, and_, update, delete, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Document, DocumentStatus, Project, Connector


class DocumentService:
    """
    Service for document operations with optimized queries.
    All batch operations use bulk queries instead of N individual queries.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============== CRUD Operations ==============

    async def create_document(
        self,
        tenant_id: UUID,
        title: str,
        content: Optional[str] = None,
        connector_id: Optional[UUID] = None,
        external_id: Optional[str] = None,
        source_url: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
        source_created_at: Optional[datetime] = None,
    ) -> Document:
        """Create a single document."""
        content_hash = self._compute_hash(content) if content else None

        doc = Document(
            tenant_id=tenant_id,
            title=title,
            content=content,
            content_hash=content_hash,
            connector_id=connector_id,
            external_id=external_id,
            source_url=source_url,
            mime_type=mime_type,
            metadata=metadata or {},
            source_created_at=source_created_at,
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def create_documents_bulk(
        self,
        tenant_id: UUID,
        documents: List[Dict[str, Any]]
    ) -> List[Document]:
        """
        Create multiple documents in a single operation.
        MUCH faster than creating one at a time (fixes N+1 issue).
        """
        docs = []
        for doc_data in documents:
            content = doc_data.get("content")
            doc = Document(
                tenant_id=tenant_id,
                title=doc_data["title"],
                content=content,
                content_hash=self._compute_hash(content) if content else None,
                connector_id=doc_data.get("connector_id"),
                external_id=doc_data.get("external_id"),
                source_url=doc_data.get("source_url"),
                mime_type=doc_data.get("mime_type"),
                metadata=doc_data.get("metadata", {}),
                source_created_at=doc_data.get("source_created_at"),
            )
            docs.append(doc)

        self.db.add_all(docs)
        await self.db.flush()
        return docs

    async def get_document(self, document_id: UUID, tenant_id: UUID) -> Optional[Document]:
        """Get a single document by ID."""
        result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    Document.tenant_id == tenant_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_documents(
        self,
        tenant_id: UUID,
        status: Optional[DocumentStatus] = None,
        project_id: Optional[UUID] = None,
        connector_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Document], int]:
        """
        Get documents with filtering and pagination.
        Returns both documents and total count in efficient queries.
        """
        # Build base query
        query = select(Document).where(Document.tenant_id == tenant_id)
        count_query = select(func.count(Document.id)).where(Document.tenant_id == tenant_id)

        # Apply filters
        if status:
            query = query.where(Document.status == status)
            count_query = count_query.where(Document.status == status)
        if project_id:
            query = query.where(Document.project_id == project_id)
            count_query = count_query.where(Document.project_id == project_id)
        if connector_id:
            query = query.where(Document.connector_id == connector_id)
            count_query = count_query.where(Document.connector_id == connector_id)

        # Execute count query
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Execute main query with pagination
        query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        documents = result.scalars().all()

        return list(documents), total

    async def get_documents_by_ids(
        self,
        document_ids: List[UUID],
        tenant_id: UUID
    ) -> List[Document]:
        """
        Get multiple documents by IDs in a single query.
        Fixes the N+1 issue of loading documents one by one.
        """
        if not document_ids:
            return []

        result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.id.in_(document_ids),
                    Document.tenant_id == tenant_id
                )
            )
        )
        return list(result.scalars().all())

    # ============== Bulk Operations (Fix N+1 Issues) ==============

    async def bulk_classify_documents(
        self,
        document_ids: List[UUID],
        classification: str,
        confidence: float = 1.0
    ) -> int:
        """
        Classify multiple documents in a single query.
        Original code did 100 docs = 100 queries. This does 1 query.
        """
        if not document_ids:
            return 0

        result = await self.db.execute(
            update(Document)
            .where(Document.id.in_(document_ids))
            .values(
                classification=classification,
                classification_confidence=confidence,
                status=DocumentStatus.CLASSIFIED,
                updated_at=datetime.utcnow()
            )
        )
        return result.rowcount

    async def bulk_delete_documents(
        self,
        document_ids: List[UUID],
        tenant_id: UUID,
        batch_size: int = 100
    ) -> int:
        """
        Delete multiple documents with batching to prevent table locks.
        Original code did 50 docs = 150 queries. This batches efficiently.
        """
        if not document_ids:
            return 0

        total_deleted = 0

        # Process in batches to prevent long table locks
        for i in range(0, len(document_ids), batch_size):
            batch = document_ids[i:i + batch_size]
            result = await self.db.execute(
                delete(Document).where(
                    and_(
                        Document.id.in_(batch),
                        Document.tenant_id == tenant_id
                    )
                )
            )
            total_deleted += result.rowcount

        return total_deleted

    async def bulk_update_status(
        self,
        document_ids: List[UUID],
        status: DocumentStatus
    ) -> int:
        """Update status for multiple documents in one query."""
        if not document_ids:
            return 0

        result = await self.db.execute(
            update(Document)
            .where(Document.id.in_(document_ids))
            .values(status=status, updated_at=datetime.utcnow())
        )
        return result.rowcount

    async def bulk_assign_project(
        self,
        document_ids: List[UUID],
        project_id: UUID
    ) -> int:
        """Assign multiple documents to a project in one query."""
        if not document_ids:
            return 0

        result = await self.db.execute(
            update(Document)
            .where(Document.id.in_(document_ids))
            .values(project_id=project_id, updated_at=datetime.utcnow())
        )
        return result.rowcount

    # ============== Deduplication ==============

    async def find_duplicates_by_hash(
        self,
        content_hashes: List[str],
        tenant_id: UUID
    ) -> set[str]:
        """
        Find existing documents by content hash in a single query.
        Fixes the sync deduplication N+1 issue.
        """
        if not content_hashes:
            return set()

        result = await self.db.execute(
            select(Document.content_hash).where(
                and_(
                    Document.content_hash.in_(content_hashes),
                    Document.tenant_id == tenant_id
                )
            )
        )
        return {row[0] for row in result.fetchall()}

    async def find_by_external_ids(
        self,
        external_ids: List[str],
        connector_id: UUID
    ) -> Dict[str, Document]:
        """
        Find existing documents by external IDs in a single query.
        Returns a dict mapping external_id -> Document.
        """
        if not external_ids:
            return {}

        result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.external_id.in_(external_ids),
                    Document.connector_id == connector_id
                )
            )
        )
        return {doc.external_id: doc for doc in result.scalars().all()}

    # ============== Statistics (Aggregated Queries) ==============

    async def get_document_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        Get document statistics in a single aggregated query.
        Original code did 8+ separate COUNT queries. This does 1.
        """
        result = await self.db.execute(
            select(
                func.count(Document.id).label("total"),
                func.sum(case((Document.status == DocumentStatus.PENDING, 1), else_=0)).label("pending"),
                func.sum(case((Document.status == DocumentStatus.PROCESSING, 1), else_=0)).label("processing"),
                func.sum(case((Document.status == DocumentStatus.CLASSIFIED, 1), else_=0)).label("classified"),
                func.sum(case((Document.status == DocumentStatus.INDEXED, 1), else_=0)).label("indexed"),
                func.sum(case((Document.status == DocumentStatus.FAILED, 1), else_=0)).label("failed"),
                func.sum(case((Document.is_indexed == True, 1), else_=0)).label("in_vector_db"),
            ).where(Document.tenant_id == tenant_id)
        )
        row = result.fetchone()

        return {
            "total": row.total or 0,
            "pending": row.pending or 0,
            "processing": row.processing or 0,
            "classified": row.classified or 0,
            "indexed": row.indexed or 0,
            "failed": row.failed or 0,
            "in_vector_db": row.in_vector_db or 0,
        }

    # ============== Helpers ==============

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()

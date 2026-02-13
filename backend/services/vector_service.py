"""
Vector store service using Pinecone for similarity search.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID

from pinecone import Pinecone

from core.config import get_settings

settings = get_settings()


class VectorService:
    """Service for vector storage and similarity search using Pinecone."""

    def __init__(self):
        self._client = None
        self._index = None
        self._ai_service = None

    @property
    def client(self) -> Pinecone:
        """Lazy load Pinecone client."""
        if self._client is None:
            self._client = Pinecone(api_key=settings.PINECONE_API_KEY)
        return self._client

    @property
    def index(self):
        """Get Pinecone index."""
        if self._index is None:
            self._index = self.client.Index(settings.PINECONE_INDEX_NAME)
        return self._index

    @property
    def ai_service(self):
        """Lazy load AI service for embeddings."""
        if self._ai_service is None:
            from services.ai_service import AIService
            self._ai_service = AIService()
        return self._ai_service

    async def upsert_document(
        self,
        document_id: str,
        content: str,
        tenant_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Index a single document in the vector store.
        Returns the vector ID.
        """
        # Create embedding
        embedding = await self.ai_service.create_embedding(content)

        # Prepare metadata
        vector_metadata = {
            "tenant_id": tenant_id,
            "content": content[:1000],  # Store truncated content for retrieval
            **(metadata or {})
        }

        # Upsert to Pinecone
        self.index.upsert(
            vectors=[{
                "id": document_id,
                "values": embedding,
                "metadata": vector_metadata
            }],
            namespace=tenant_id
        )

        return document_id

    async def upsert_documents_batch(
        self,
        documents: List[Dict[str, Any]],
        tenant_id: str,
        batch_size: int = 100
    ) -> List[str]:
        """
        Index multiple documents efficiently.
        Uses batched embeddings and upserts.
        """
        if not documents:
            return []

        # Extract content for embedding
        contents = [doc.get("content", "") for doc in documents]

        # Create embeddings in batch
        embeddings = await self.ai_service.create_embeddings_batch(contents, batch_size)

        # Prepare vectors
        vectors = []
        ids = []
        for doc, embedding in zip(documents, embeddings):
            doc_id = str(doc.get("id", ""))
            ids.append(doc_id)

            vectors.append({
                "id": doc_id,
                "values": embedding,
                "metadata": {
                    "tenant_id": tenant_id,
                    "title": doc.get("title", ""),
                    "content": doc.get("content", "")[:1000],
                    "source_url": doc.get("source_url"),
                    "created_at": doc.get("created_at"),
                }
            })

        # Upsert in batches
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=tenant_id)

        return ids

    async def search(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        Returns top_k most relevant documents.
        """
        # Create query embedding
        query_embedding = await self.ai_service.create_embedding(query)

        # Build filter
        pinecone_filter = filter_metadata or {}

        # Search
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=tenant_id,
            filter=pinecone_filter if pinecone_filter else None,
            include_metadata=True
        )

        # Format results
        documents = []
        for match in results.matches:
            doc = {
                "id": match.id,
                "score": match.score,
                **match.metadata
            }
            documents.append(doc)

        return documents

    async def delete_document(self, document_id: str, tenant_id: str) -> bool:
        """Delete a document from the vector store."""
        try:
            self.index.delete(ids=[document_id], namespace=tenant_id)
            return True
        except Exception:
            return False

    async def delete_documents_batch(
        self,
        document_ids: List[str],
        tenant_id: str
    ) -> int:
        """Delete multiple documents from the vector store."""
        if not document_ids:
            return 0

        try:
            self.index.delete(ids=document_ids, namespace=tenant_id)
            return len(document_ids)
        except Exception:
            return 0

    async def delete_tenant_data(self, tenant_id: str) -> bool:
        """Delete all data for a tenant."""
        try:
            self.index.delete(delete_all=True, namespace=tenant_id)
            return True
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "namespaces": stats.namespaces
            }
        except Exception:
            return {"error": "Unable to fetch stats"}

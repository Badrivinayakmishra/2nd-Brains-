"""
Chat service with RAG (Retrieval Augmented Generation) support.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator
from uuid import UUID
import json

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import ChatSession, ChatMessage, Document
from core.config import get_settings

settings = get_settings()


class ChatService:
    """Service for chat operations with RAG support."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._ai_client = None
        self._vector_store = None

    @property
    def ai_client(self):
        """Lazy load AI client."""
        if self._ai_client is None:
            from services.ai_service import AIService
            self._ai_client = AIService()
        return self._ai_client

    @property
    def vector_store(self):
        """Lazy load vector store."""
        if self._vector_store is None:
            from services.vector_service import VectorService
            self._vector_store = VectorService()
        return self._vector_store

    # ============== Session Management ==============

    async def create_session(self, tenant_id: UUID, title: Optional[str] = None) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            tenant_id=tenant_id,
            title=title or "New Chat"
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session(self, session_id: UUID, tenant_id: UUID) -> Optional[ChatSession]:
        """Get a chat session with messages."""
        result = await self.db.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(
                and_(
                    ChatSession.id == session_id,
                    ChatSession.tenant_id == tenant_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_sessions(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0
    ) -> List[ChatSession]:
        """Get chat sessions for a tenant."""
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.tenant_id == tenant_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def delete_session(self, session_id: UUID, tenant_id: UUID) -> bool:
        """Delete a chat session."""
        session = await self.get_session(session_id, tenant_id)
        if session:
            await self.db.delete(session)
            return True
        return False

    # ============== Message Operations ==============

    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        sources: Optional[List[str]] = None
    ) -> ChatMessage:
        """Add a message to a session."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources
        )
        self.db.add(message)

        # Update session timestamp
        session = await self.db.get(ChatSession, session_id)
        if session:
            session.updated_at = datetime.utcnow()

        await self.db.flush()
        return message

    async def get_messages(
        self,
        session_id: UUID,
        limit: int = 50
    ) -> List[ChatMessage]:
        """Get messages for a session."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ============== RAG Chat ==============

    async def chat(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process a chat message with RAG.
        1. Store user message
        2. Search relevant documents
        3. Generate AI response with context
        4. Store and return response
        """
        # Store user message
        await self.add_message(session_id, "user", user_message)

        # Get chat history for context
        messages = await self.get_messages(session_id, limit=10)
        history = [{"role": m.role, "content": m.content} for m in messages]

        # Search for relevant documents
        relevant_docs = await self.vector_store.search(
            query=user_message,
            tenant_id=str(tenant_id),
            top_k=5
        )

        # Build context from documents
        context = self._build_context(relevant_docs)

        # Generate response
        response = await self.ai_client.generate_response(
            messages=history,
            context=context,
            system_prompt=self._get_system_prompt()
        )

        # Extract source document IDs
        source_ids = [doc.get("id") for doc in relevant_docs if doc.get("id")]

        # Store assistant message
        assistant_message = await self.add_message(
            session_id,
            "assistant",
            response,
            sources=source_ids
        )

        return {
            "message": response,
            "sources": relevant_docs,
            "message_id": str(assistant_message.id)
        }

    async def chat_stream(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response for better UX.
        Yields chunks of the response as they're generated.
        """
        # Store user message
        await self.add_message(session_id, "user", user_message)

        # Get chat history
        messages = await self.get_messages(session_id, limit=10)
        history = [{"role": m.role, "content": m.content} for m in messages]

        # Search for relevant documents
        relevant_docs = await self.vector_store.search(
            query=user_message,
            tenant_id=str(tenant_id),
            top_k=5
        )

        context = self._build_context(relevant_docs)

        # Stream response
        full_response = ""
        async for chunk in self.ai_client.generate_response_stream(
            messages=history,
            context=context,
            system_prompt=self._get_system_prompt()
        ):
            full_response += chunk
            yield chunk

        # Store complete response
        source_ids = [doc.get("id") for doc in relevant_docs if doc.get("id")]
        await self.add_message(session_id, "assistant", full_response, sources=source_ids)

    def _build_context(self, documents: List[Dict]) -> str:
        """Build context string from retrieved documents."""
        if not documents:
            return ""

        context_parts = []
        for i, doc in enumerate(documents, 1):
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:1000]  # Truncate long content
            context_parts.append(f"[{i}] {title}:\n{content}")

        return "\n\n".join(context_parts)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the chat."""
        return """You are a helpful AI assistant with access to the user's knowledge base.
Your role is to answer questions based on the provided context from their documents.

Guidelines:
1. Use the provided context to answer questions accurately
2. If the context doesn't contain enough information, say so honestly
3. Cite sources by referring to the document numbers [1], [2], etc.
4. Be concise but thorough
5. If asked about something not in the context, you can use your general knowledge but note that it's not from their documents

Always be helpful, accurate, and respect the user's privacy."""

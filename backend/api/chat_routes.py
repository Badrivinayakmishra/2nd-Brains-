"""
Chat API routes with streaming support.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, Tenant
from services.chat_service import ChatService
from api.auth_routes import get_current_tenant

router = APIRouter(prefix="/chat", tags=["Chat"])


# ============== Schemas ==============

class SessionCreate(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    sources: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    sources: List[dict]
    message_id: str


# ============== Routes ==============

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """List chat sessions."""
    service = ChatService(db)
    sessions = await service.get_sessions(tenant.id, limit, offset)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session."""
    service = ChatService(db)
    session = await service.create_session(tenant.id, data.title)
    return SessionResponse.model_validate(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Get a chat session."""
    service = ChatService(db)
    session = await service.get_session(session_id, tenant.id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return SessionResponse.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Delete a chat session."""
    service = ChatService(db)
    deleted = await service.delete_session(session_id, tenant.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a session."""
    service = ChatService(db)

    # Verify session belongs to tenant
    session = await service.get_session(session_id, tenant.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    messages = await service.get_messages(session_id)
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat(
    session_id: UUID,
    request: ChatRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message and get AI response with RAG.
    Uses document context from vector store.
    """
    service = ChatService(db)

    # Verify session
    session = await service.get_session(session_id, tenant.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    result = await service.chat(session_id, tenant.id, request.message)
    return ChatResponse(**result)


@router.post("/sessions/{session_id}/chat/stream")
async def chat_stream(
    session_id: UUID,
    request: ChatRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message and get streaming AI response.
    Better UX for longer responses.
    """
    service = ChatService(db)

    # Verify session
    session = await service.get_session(session_id, tenant.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    async def generate():
        async for chunk in service.chat_stream(session_id, tenant.id, request.message):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

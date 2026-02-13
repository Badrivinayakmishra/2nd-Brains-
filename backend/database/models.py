"""
Database models with proper indexes for performance.
Fixes N+1 query issues by using relationships with lazy loading strategies.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, ForeignKey,
    Index, Enum as SQLEnum, JSON, Float
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

Base = declarative_base()


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    INDEXED = "indexed"
    FAILED = "failed"


class GapStatus(str, enum.Enum):
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


class ConnectorType(str, enum.Enum):
    GOOGLE_DRIVE = "google_drive"
    GMAIL = "gmail"
    SLACK = "slack"
    NOTION = "notion"
    ONEDRIVE = "onedrive"
    GITHUB = "github"
    WEBSCRAPER = "webscraper"
    EMAIL_FORWARDING = "email_forwarding"


# ============== User & Auth ==============

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Null for OAuth users
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="owner", uselist=False)
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_user_expires", "user_id", "expires_at"),
    )


# ============== Tenant (Multi-tenancy) ==============

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    connectors = relationship("Connector", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_gaps = relationship("KnowledgeGap", back_populates="tenant", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="tenant", cascade="all, delete-orphan")


# ============== Connectors ==============

class Connector(Base):
    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    connector_type = Column(SQLEnum(ConnectorType), nullable=False)
    name = Column(String(255), nullable=False)
    credentials = Column(JSON)  # Encrypted in production
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    sync_status = Column(String(50), default="idle")
    sync_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="connectors")
    documents = relationship("Document", back_populates="connector")

    __table_args__ = (
        Index("ix_connectors_tenant_type", "tenant_id", "connector_type"),
        Index("ix_connectors_tenant_active", "tenant_id", "is_active"),
    )


# ============== Documents ==============

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    connector_id = Column(UUID(as_uuid=True), ForeignKey("connectors.id", ondelete="SET NULL"))
    external_id = Column(String(500))  # ID from external source

    title = Column(String(500), nullable=False)
    content = Column(Text)
    content_hash = Column(String(64))  # For deduplication
    source_url = Column(String(2000))
    mime_type = Column(String(100))

    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING)
    classification = Column(String(50))  # work, personal, etc.
    classification_confidence = Column(Float)

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"))

    metadata = Column(JSON)  # Flexible metadata storage

    # Vector embedding reference
    vector_id = Column(String(100))
    is_indexed = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source_created_at = Column(DateTime)  # Original creation date from source

    tenant = relationship("Tenant", back_populates="documents")
    connector = relationship("Connector", back_populates="documents")
    project = relationship("Project", back_populates="documents")

    # Critical indexes for performance (fixes original N+1 issues)
    __table_args__ = (
        Index("ix_documents_external_id", "external_id"),
        Index("ix_documents_connector_external", "connector_id", "external_id"),
        Index("ix_documents_tenant_status", "tenant_id", "status"),
        Index("ix_documents_tenant_project", "tenant_id", "project_id"),
        Index("ix_documents_content_hash", "content_hash"),
        Index("ix_documents_tenant_indexed", "tenant_id", "is_indexed"),
    )


# ============== Projects ==============

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7))  # Hex color
    is_auto_detected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="projects")
    documents = relationship("Document", back_populates="project")

    __table_args__ = (
        Index("ix_projects_tenant", "tenant_id"),
    )


# ============== Knowledge Gaps ==============

class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    question = Column(Text, nullable=False)
    category = Column(String(100))
    priority = Column(Integer, default=1)  # 1-5
    status = Column(SQLEnum(GapStatus), default=GapStatus.OPEN)

    answer = Column(Text)
    answered_at = Column(DateTime)

    source_document_ids = Column(JSON)  # List of document IDs that triggered this gap

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="knowledge_gaps")

    # Critical indexes for performance (fixes original issues)
    __table_args__ = (
        Index("ix_knowledge_gaps_tenant_status", "tenant_id", "status"),
        Index("ix_knowledge_gaps_tenant_category", "tenant_id", "category"),
        Index("ix_knowledge_gaps_tenant_priority", "tenant_id", "priority"),
    )


# ============== Chat History ==============

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_chat_sessions_tenant", "tenant_id"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    sources = Column(JSON)  # Referenced document IDs
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("ix_chat_messages_session", "session_id"),
    )


# ============== Sync Progress Tracking ==============

class SyncProgress(Base):
    __tablename__ = "sync_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connector_id = Column(UUID(as_uuid=True), ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False)

    status = Column(String(50), default="idle")  # idle, syncing, completed, failed
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    indexed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)

    current_step = Column(String(255))
    error_message = Column(Text)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    __table_args__ = (
        Index("ix_sync_progress_connector", "connector_id"),
    )

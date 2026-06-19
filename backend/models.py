"""
SQLAlchemy ORM models for Knowledge Vault
Maps to production PostgreSQL schema
"""

from datetime import datetime, timezone
from typing import Optional, List
from decimal import Decimal
import uuid

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DECIMAL, DateTime,
    ForeignKey, TIMESTAMP, ARRAY, Index, func, UniqueConstraint,
    CheckConstraint, JSON, TypeDecorator
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# PostgreSQL UUID type
class GUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        elif isinstance(value, uuid.UUID):
            return str(value)
        else:
            return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


Base = declarative_base()


# ============================================================================
# USER MODEL
# ============================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    external_auth_id = Column(String(255), unique=True, nullable=False)
    auth_provider = Column(
        String(50),
        nullable=False,
        default="auth0",
        comment="auth0, firebase, cognito, custom"
    )

    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255))
    avatar_url = Column(Text)

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_verified_email = Column(Boolean, default=False, nullable=False)
    subscription_tier = Column(
        String(50),
        default="free",
        nullable=False,
        comment="free, pro, enterprise"
    )

    storage_quota_mb = Column(Integer, default=1000, nullable=False)
    storage_used_mb = Column(Integer, default=0, nullable=False)
    api_calls_limit = Column(Integer, default=1000, nullable=False)
    api_calls_used = Column(Integer, default=0, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    last_login_at = Column(TIMESTAMP(timezone=True))
    deleted_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    links = relationship("Link", back_populates="user", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="user", cascade="all, delete-orphan")
    search_queries = relationship("SearchQuery", back_populates="user", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="user", cascade="all, delete-orphan")
    api_tokens = relationship("APIToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


# ============================================================================
# LINK MODEL
# ============================================================================
class Link(Base):
    __tablename__ = "links"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core URL
    original_url = Column(Text, nullable=False)
    normalized_url = Column(String(2048), unique=True, nullable=False, index=True)

    # Platform & classification
    platform = Column(String(50), index=True)
    category_hierarchy = Column(String(500))
    is_e_commerce = Column(Boolean, default=False)
    is_social_media = Column(Boolean, default=False)

    # Extracted metadata
    title = Column(String(1024))
    description = Column(Text)
    author = Column(String(255))
    published_date = Column(TIMESTAMP(timezone=True))

    # Media
    thumbnail_url = Column(Text)
    og_image_url = Column(Text)

    # Content extraction
    full_text_snippet = Column(Text)
    headings_json = Column(JSON)
    paragraphs_json = Column(JSON)

    # E-commerce metadata
    price = Column(DECIMAL(12, 2))
    currency = Column(String(3))  # ISO 4217
    rating = Column(DECIMAL(3, 2))
    availability = Column(String(100))

    # User metadata
    custom_notes = Column(Text)
    user_tags = Column(JSON, default=[])
    
    # AI Enrichment
    ai_summary = Column(Text)
    ai_tags = Column(JSON, default=[])
    ai_processed = Column(Boolean, default=False, nullable=False, index=True)

    # Vector reference
    embedding_id = Column(String(255))
    embedding_model = Column(String(100), default="text-embedding-3-small")
    vector_dimension = Column(Integer, default=1536)

    # Lifecycle
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    last_accessed_at = Column(TIMESTAMP(timezone=True))
    deleted_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    user = relationship("User", back_populates="links")
    embedding = relationship("Embedding", back_populates="link", uselist=False)
    collections = relationship(
        "Collection",
        secondary="link_collections",
        back_populates="links"
    )

    __table_args__ = (
        Index("idx_links_user_created", "user_id", "created_at"),
        Index("idx_links_user_platform", "user_id", "platform"),
        Index("idx_links_user_ai_processed", "user_id", "ai_processed"),
    )

    def __repr__(self):
        return f"<Link {self.title or self.normalized_url}>"


# ============================================================================
# EMBEDDING MODEL
# ============================================================================
class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    link_id = Column(GUID(), ForeignKey("links.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    vector_db_id = Column(String(255), unique=True, nullable=False, index=True)
    vector_db_provider = Column(
        String(50),
        nullable=False,
        default="pinecone",
        comment="qdrant, pinecone, weaviate"
    )

    model_name = Column(String(100), default="text-embedding-3-small", nullable=False)
    dimension = Column(Integer, default=1536, nullable=False)

    embedded_text = Column(Text, nullable=False)
    embedded_content_type = Column(String(50), default="summary+tags")

    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True))

    is_synced = Column(Boolean, default=True, nullable=False)
    sync_error = Column(Text)

    # Relationships
    link = relationship("Link", back_populates="embedding")
    user = relationship("User", back_populates="embeddings")

    __table_args__ = (
        Index("idx_embeddings_user_created", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<Embedding {self.vector_db_id}>"


# ============================================================================
# SEARCH QUERY MODEL
# ============================================================================
class SearchQuery(Base):
    __tablename__ = "search_queries"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    query_text = Column(Text, nullable=False)
    query_embedding_id = Column(String(255))

    results_count = Column(Integer, default=0)
    top_result_link_ids = Column(JSON, default=[])

    ai_response = Column(Text)
    ai_model = Column(String(100), default="gpt-4o-mini")
    response_generated = Column(Boolean, default=False, index=True)

    user_satisfaction_rating = Column(Integer)
    is_helpful = Column(Boolean)

    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="search_queries")

    __table_args__ = (
        Index("idx_search_queries_user_response", "user_id", "response_generated"),
        CheckConstraint("user_satisfaction_rating IS NULL OR (user_satisfaction_rating >= 1 AND user_satisfaction_rating <= 5)"),
    )

    def __repr__(self):
        return f"<SearchQuery {self.query_text[:50]}>"


# ============================================================================
# COLLECTION MODEL
# ============================================================================
class Collection(Base):
    __tablename__ = "collections"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text)
    color_hex = Column(String(7))
    icon = Column(String(50))

    is_public = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)

    display_order = Column(Integer, default=0)

    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    user = relationship("User", back_populates="collections")
    links = relationship(
        "Link",
        secondary="link_collections",
        back_populates="collections"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_collection_name"),
    )

    def __repr__(self):
        return f"<Collection {self.name}>"


# ============================================================================
# LINK-COLLECTION ASSOCIATION
# ============================================================================
class LinkCollection(Base):
    __tablename__ = "link_collections"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    link_id = Column(GUID(), ForeignKey("links.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(GUID(), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)

    position = Column(Integer)

    added_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("link_id", "collection_id", name="uq_link_collection"),
    )


# ============================================================================
# SHARE INTENT MODEL
# ============================================================================
class ShareIntent(Base):
    __tablename__ = "share_intents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), index=True)

    shared_url = Column(Text, nullable=False)
    shared_text = Column(String(500))
    source_app = Column(String(100))

    status = Column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="pending, processing, saved, failed"
    )
    created_link_id = Column(GUID(), ForeignKey("links.id", ondelete="SET NULL"))

    error_message = Column(Text)

    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False, index=True)
    processed_at = Column(TIMESTAMP(timezone=True))

    def __repr__(self):
        return f"<ShareIntent {self.shared_url}>"


# ============================================================================
# AUDIT LOG MODEL
# ============================================================================
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), index=True)

    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50))
    resource_id = Column(GUID())

    ip_address = Column(String(45))
    user_agent = Column(Text)

    details = Column(JSON)

    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_logs_action_created", "action", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action}>"


# ============================================================================
# API TOKEN MODEL
# ============================================================================
class APIToken(Base):
    __tablename__ = "api_tokens"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    token_hash = Column(String(64), unique=True, nullable=False)
    name = Column(String(255))

    scopes = Column(JSON, default=["links:read", "links:write"])

    rate_limit_per_minute = Column(Integer, default=60)

    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    last_used_at = Column(TIMESTAMP(timezone=True))
    expires_at = Column(TIMESTAMP(timezone=True))
    revoked_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    user = relationship("User", back_populates="api_tokens")

    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        return (
            self.revoked_at is None and
            (self.expires_at is None or self.expires_at > now)
        )

    def __repr__(self):
        return f"<APIToken {self.name}>"


# ============================================================================
# SYSTEM CONFIG MODEL
# ============================================================================
class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    config_key = Column(String(255), unique=True, nullable=False, index=True)
    config_value = Column(JSON, nullable=False)
    description = Column(Text)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    updated_by = Column(String(255))

    def __repr__(self):
        return f"<SystemConfig {self.config_key}>"

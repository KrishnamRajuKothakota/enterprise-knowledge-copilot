import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, Enum, ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


def new_uuid():
    return str(uuid.uuid4())


# ── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    junior_engineer = "junior_engineer"
    l1_support = "l1_support"
    lead = "lead"


class SourceType(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    pptx = "pptx"
    csv = "csv"
    html = "html"
    confluence = "confluence"
    jira = "jira"


class TicketSource(str, enum.Enum):
    jira = "jira"
    servicenow = "servicenow"
    csv = "csv"


class TicketStatus(str, enum.Enum):
    open = "open"
    received = "received"
    searching = "searching"
    resolving = "resolving"
    suggestion_sent = "suggestion_sent"
    resolved = "resolved"
    escalating = "escalating"
    escalated_human = "escalated_human"


class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RelationshipType(str, enum.Enum):
    related_to = "RELATED_TO"
    resolves = "RESOLVES"
    belongs_to = "BELONGS_TO"


class FeedbackRating(str, enum.Enum):
    up = "up"
    down = "down"


# ── Tables ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.junior_engineer)
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sessions = relationship("QuerySession", back_populates="user")
    query_logs = relationship("QueryLog", back_populates="user")
    feedbacks = relationship("Feedback", back_populates="user")
    tickets = relationship("Ticket", back_populates="assigned_to")


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)
    owner_user_id = Column(UUID(as_uuid=False), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documents = relationship("Document", back_populates="project")


class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    title = Column(Text, nullable=False)
    source_type = Column(Enum(SourceType), nullable=False)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_modified = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, nullable=True)
    language = Column(String(10), default="en", nullable=False)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.project_id"), nullable=True)
    # RBAC fields (Artifact 4 schema additions)
    namespace = Column(String(100), nullable=True)          # e.g. "hr", "devops"
    access_roles = Column(JSON, default=list, nullable=False)  # ["junior_engineer","lead"]
    status = Column(String(50), default="active", nullable=False)

    project = relationship("Project", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    redaction_audits = relationship("RedactionAudit", back_populates="document")

    __table_args__ = (
        Index("ix_documents_namespace", "namespace"),
        Index("ix_documents_source_type", "source_type"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    doc_id = Column(UUID(as_uuid=False), ForeignKey("documents.doc_id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_title = Column(Text, nullable=True)
    heading_path = Column(Text, nullable=True)   # e.g. "Chapter 1 > Section 2"
    token_count = Column(Integer, nullable=True)

    document = relationship("Document", back_populates="chunks")
    embedding = relationship("Embedding", back_populates="chunk", uselist=False,
                             cascade="all, delete-orphan")
    entity_mentions = relationship("EntityMention", back_populates="chunk")

    __table_args__ = (
        Index("ix_chunks_doc_id", "doc_id"),
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    embedding_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    chunk_id = Column(UUID(as_uuid=False), ForeignKey("chunks.chunk_id"), nullable=False,
                      unique=True)
    model_name = Column(String(255), nullable=False,
                        default="sentence-transformers/all-MiniLM-L6-v2")
    vector = Column(JSON, nullable=False)        # stored as list; FAISS holds the fast index
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    faiss_index_id = Column(Integer, nullable=True)   # position in FAISS flat index

    chunk = relationship("Chunk", back_populates="embedding")


class RedactionAudit(Base):
    __tablename__ = "redaction_audit"

    audit_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    doc_id = Column(UUID(as_uuid=False), ForeignKey("documents.doc_id"), nullable=False)
    pii_type = Column(String(100), nullable=False)      # PERSON, EMAIL, AADHAAR, PAN …
    token_replacement = Column(String(100), nullable=False)  # [PERSON_1]
    redacted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="redaction_audits")

    __table_args__ = (
        Index("ix_redaction_audit_doc_id", "doc_id"),
    )


class Entity(Base):
    __tablename__ = "entities"

    entity_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    canonical_name = Column(String(512), nullable=False, unique=True)
    entity_type = Column(String(100), nullable=False)   # Technology, Project, Team, SOP, Ticket
    aliases = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    mentions = relationship("EntityMention", back_populates="entity")
    source_relationships = relationship("EntityRelationship",
                                        foreign_keys="EntityRelationship.source_entity_id",
                                        back_populates="source_entity")
    target_relationships = relationship("EntityRelationship",
                                        foreign_keys="EntityRelationship.target_entity_id",
                                        back_populates="target_entity")


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    mention_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    entity_id = Column(UUID(as_uuid=False), ForeignKey("entities.entity_id"), nullable=False)
    chunk_id = Column(UUID(as_uuid=False), ForeignKey("chunks.chunk_id"), nullable=False)
    confidence_score = Column(Float, nullable=True)

    entity = relationship("Entity", back_populates="mentions")
    chunk = relationship("Chunk", back_populates="entity_mentions")

    __table_args__ = (
        Index("ix_entity_mentions_entity_id", "entity_id"),
        Index("ix_entity_mentions_chunk_id", "chunk_id"),
    )


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    rel_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    source_entity_id = Column(UUID(as_uuid=False), ForeignKey("entities.entity_id"),
                               nullable=False)
    target_entity_id = Column(UUID(as_uuid=False), ForeignKey("entities.entity_id"),
                               nullable=False)
    relationship_type = Column(Enum(RelationshipType), nullable=False)
    weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source_entity = relationship("Entity", foreign_keys=[source_entity_id],
                                  back_populates="source_relationships")
    target_entity = relationship("Entity", foreign_keys=[target_entity_id],
                                  back_populates="target_relationships")

    __table_args__ = (
        Index("ix_entity_rel_source", "source_entity_id"),
        Index("ix_entity_rel_target", "target_entity_id"),
    )


class QuerySession(Base):
    __tablename__ = "query_sessions"

    session_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=False)
    context_window = Column(JSON, default=list, nullable=False)  # conversation history

    user = relationship("User", back_populates="sessions")
    query_logs = relationship("QueryLog", back_populates="session")


class QueryLog(Base):
    __tablename__ = "query_logs"

    query_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("query_sessions.session_id"),
                        nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.user_id"), nullable=False)
    query_text = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(JSON, default=list, nullable=False)
    response_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="answered", nullable=False)  # answered/fallback/error
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("QuerySession", back_populates="query_logs")
    user = relationship("User", back_populates="query_logs")
    feedback = relationship("Feedback", back_populates="query_log", uselist=False)

    __table_args__ = (
        Index("ix_query_logs_user_id", "user_id"),
        Index("ix_query_logs_created_at", "created_at"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    query_id = Column(UUID(as_uuid=False), ForeignKey("query_logs.query_id"), nullable=False,
                      unique=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.user_id"), nullable=False)
    rating = Column(Enum(FeedbackRating), nullable=False)
    comment = Column(Text, nullable=True)
    llm_judge_score = Column(Float, nullable=True)   # filled by nightly batch
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    query_log = relationship("QueryLog", back_populates="feedback")
    user = relationship("User", back_populates="feedbacks")


class RagasEvaluation(Base):
    __tablename__ = "ragas_evaluations"

    eval_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    run_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    faithfulness = Column(Float, nullable=False)
    context_precision = Column(Float, nullable=False)
    answer_relevancy = Column(Float, nullable=False)
    context_recall = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)


class Ticket(Base):
    """Required by TicketAutoResolverAgent — Artifact 4 schema addition."""
    __tablename__ = "tickets"

    ticket_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    external_id = Column(String(100), nullable=True)    # "JRA-4521" / "INC-8834"
    source = Column(Enum(TicketSource), nullable=False, default=TicketSource.csv)
    summary = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TicketStatus), nullable=False, default=TicketStatus.open)
    priority = Column(Enum(TicketPriority), nullable=False, default=TicketPriority.medium)
    resolution_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    assigned_to_user_id = Column(UUID(as_uuid=False), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    assigned_to = relationship("User", back_populates="tickets")
    similarities = relationship("TicketSimilarity",
                                foreign_keys="TicketSimilarity.ticket_id",
                                back_populates="ticket",
                                cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_external_id", "external_id"),
    )


class TicketSimilarity(Base):
    """Junction table — Artifact 4 schema addition replacing JSON array anti-pattern."""
    __tablename__ = "ticket_similarities"

    similarity_id = Column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.ticket_id"), nullable=False)
    similar_ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.ticket_id"),
                                nullable=False)
    similarity_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ticket = relationship("Ticket", foreign_keys=[ticket_id], back_populates="similarities")

    __table_args__ = (
        UniqueConstraint("ticket_id", "similar_ticket_id", name="uq_ticket_similarity"),
        Index("ix_ticket_similarities_ticket_id", "ticket_id"),
    )
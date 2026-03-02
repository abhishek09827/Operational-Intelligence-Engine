from sqlalchemy import Column, Integer, String, DateTime, Float, Text, JSON
from sqlalchemy.sql import func
from app.models.base import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="Open", index=True)
    severity = Column(String, default="Medium")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Analysis results
    root_cause = Column(Text, nullable=True)
    suggested_fix = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # RAG Embeddings stored as JSON string (list of floats)
    # This avoids dimension mismatch issues and makes the system more flexible
    embedding = Column(JSON, nullable=True)


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String, unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    level = Column(String, default="ERROR", index=True)
    category = Column(String, index=True, nullable=False)  # API_ERROR, PAYMENT_FAILURE, etc.
    
    # Common fields
    service_name = Column(String, index=True, nullable=False)
    environment = Column(String, default="production")
    request_id = Column(String, index=True)
    
    # Category-specific fields (stored as JSON for flexibility)
    api_error = Column(JSON, nullable=True)
    payment_failure = Column(JSON, nullable=True)
    timeout = Column(JSON, nullable=True)
    rate_limit = Column(JSON, nullable=True)
    dependency_failure = Column(JSON, nullable=True)
    
    # Additional context
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
